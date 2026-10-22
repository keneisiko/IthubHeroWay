from __future__ import annotations

from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.utils.html import format_html

from apps.integrations.services.lxp_group_import import slug
from apps.notifications.services import events
from apps.operations.admin_actions import FrozenWhileAccrualsOffMixin
from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_curator, is_hq, is_superadmin, is_tutor
from apps.quests.services.quest_completion import complete_quest_idempotent

from .models import (
    Quest,
    QuestRewardTransaction,
    QuestTemplate,
    QuestVerifierKind,
    SeasonalEvent,
    SelfReportProof,
    SelfReportProofStatus,
    SquadLeaderboardSnapshot,
    UserQuestProgress,
    WeeklyFocus,
)


def _complete_quest_idempotent(user, quest, reviewer):
    progress, created = complete_quest_idempotent(
        user,
        quest,
        reason=f"Квест «{quest.title}» подтверждён куратором",
    )
    LogEntry.objects.log_action(
        user_id=reviewer.pk,
        content_type_id=ContentType.objects.get_for_model(UserQuestProgress).pk,
        object_id=progress.pk,
        object_repr=str(progress),
        action_flag=CHANGE,
        change_message=(
            f"Одобрено подтверждение по квесту «{quest.title}»: "
            + ("награда начислена." if created else "награда уже была начислена раньше.")
        ),
    )


class ExtendDeadlineForm(forms.Form):
    days = forms.IntegerField(label="На сколько дней продлить", min_value=1, max_value=60, initial=7)


# Параметры каждой проверки: (ключ, подпись, значение по умолчанию).
# Значения по умолчанию те же, что в apps/quests/services/verifiers.py.
VERIFIER_PARAMS: dict[str, tuple[tuple[str, str, float], ...]] = {
    QuestVerifierKind.HIK_ON_TIME: (
        ("deadline_hour", "Прийти до, час (если у отряда нет расписания)", 10),
        ("deadline_minute", "Прийти до, минута", 0),
        ("grace_minutes", "Допуск после начала пары, минут", 0),
    ),
    QuestVerifierKind.HIK_NO_LATE: (("days", "За сколько дней считать", 1),),
    QuestVerifierKind.LXP_ATTENDANCE: (("min_percent", "Посещаемость не ниже, %", 80),),
    QuestVerifierKind.LXP_CT_CLOSED: (
        ("min_closed", "Закрыть контрольных точек, не меньше", 1),
        ("days", "За сколько дней", 7),
    ),
    QuestVerifierKind.YOUGILE_TASKS: (
        ("min_count", "Закрыть задач, не меньше", 3),
        ("days", "За сколько дней", 7),
    ),
    QuestVerifierKind.LXP_NO_MISSES: (
        ("max_missed", "Пропусков, не больше", 0),
        ("days", "За сколько дней", 7),
    ),
    QuestVerifierKind.LATE_STREAK: (("min_days", "Дней подряд без опозданий", 7),),
    QuestVerifierKind.ATTENDANCE_STREAK: (("min_days", "Дней подряд без пропусков", 10),),
}
_ALL_PARAM_KEYS = sorted({key for spec in VERIFIER_PARAMS.values() for key, _, _ in spec})
_PARAM_LABELS = {
    "deadline_hour": "Прийти до, час",
    "deadline_minute": "Прийти до, минута",
    "grace_minutes": "Допуск, минут",
    "days": "За сколько дней",
    "min_percent": "Посещаемость не ниже, %",
    "min_closed": "КТ не меньше",
    "min_count": "Задач не меньше",
    "max_missed": "Пропусков не больше",
    "min_days": "Дней подряд",
}


def _param_help(key: str) -> str:
    users = [str(QuestVerifierKind(kind).label) for kind, spec in VERIFIER_PARAMS.items() if key in {k for k, _, _ in spec}]
    return "Для проверки: " + ", ".join(users) + ". Пусто — значение по умолчанию."


class _QuestTemplateAdminFormBase(forms.ModelForm):
    """Параметры проверки — подписанными полями вместо JSON.

    Раньше «Параметры проверки» были сырым JSON без подсказок: чтобы
    поменять порог посещаемости, нужно было знать ключ `min_percent`.
    Неизвестный ключ проверка молча игнорировала.
    """

    class Meta:
        model = QuestTemplate
        # Рейтинг из квестов не начисляется (Положение, разделы 3–7):
        # обязательное поле, куда «нужно вписать ноль», только путало.
        fields = ("title", "description", "quest_type", "reward_coins", "is_active", "code", "verifier")
        help_texts = {
            "code": "Можно оставить пустым — соберётся из названия латиницей. "
            "После запуска квеста не меняйте: по коду связаны прогресс и награды.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].required = False
        current = (self.instance.verifier_params if self.instance and self.instance.pk else None) or {}
        for key in _ALL_PARAM_KEYS:
            if key in current:
                self.initial[f"param_{key}"] = current[key]

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("code") and cleaned.get("title"):
            base = slug(cleaned["title"], "quest")
            code, n = base, 2
            while QuestTemplate.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                code, n = f"{base}-{n}", n + 1
            cleaned["code"] = code
        return cleaned

    def save(self, commit=True):
        spec = VERIFIER_PARAMS.get(self.cleaned_data.get("verifier"), ())
        params = {}
        for key, _, default in spec:
            value = self.cleaned_data.get(f"param_{key}")
            value = default if value is None else value
            params[key] = int(value) if float(value).is_integer() else float(value)
        self.instance.verifier_params = params
        self.instance.reward_rating_delta = 0
        return super().save(commit)


# Поля параметров объявлены на классе, а не добавлены в __init__: админка
# сверяет поля из fieldsets с классом формы и на «лишние» отвечает FieldError.
QuestTemplateAdminForm = type(_QuestTemplateAdminFormBase)(
    "QuestTemplateAdminForm",
    (_QuestTemplateAdminFormBase,),
    {
        "__module__": __name__,
        **{
            f"param_{key}": forms.DecimalField(
                label=_PARAM_LABELS[key], required=False, help_text=_param_help(key)
            )
            for key in _ALL_PARAM_KEYS
        },
    },
)


@admin.register(QuestTemplate)
class QuestTemplateAdmin(ManagedRoleAdminMixin):
    """Шаблоны — единственное место, где заводится новый квест.

    Ежедневные и еженедельные квесты создаются из шаблонов каждую ночь
    на свой период; остальные виды — один квест на шаблон. Прежде квест из
    шаблона самоотчёта или долгого квеста создавала только консольная
    команда: шаблон, добавленный в админке, студентам не появлялся.
    """

    form = QuestTemplateAdminForm
    actions = ("spawn_today",)

    @admin.action(description="Завести квесты на сегодня (не ждать ночи)")
    def spawn_today(self, request, queryset):
        from apps.quests.services.quest_periods import ensure_period_quests

        result = ensure_period_quests()
        self.message_user(
            request,
            f"Квесты на сегодня заведены: новых {result['created']}, уже было {result['existing']}. "
            "Это для ежедневных и еженедельных шаблонов; остальные создаются при сохранении.",
        )
    list_display = ("title", "quest_type", "verifier", "reward_coins", "is_active")
    list_filter = ("quest_type", "verifier", "is_active")
    search_fields = ("code", "title")

    def get_fieldsets(self, request, obj=None):
        params = tuple(f"param_{key}" for key in _ALL_PARAM_KEYS)
        return (
            (None, {"fields": ("title", "description", "quest_type", "reward_coins", "is_active", "code")}),
            ("Как проверяется", {"fields": ("verifier", *params)}),
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from apps.quests.services.quest_periods import PERIODIC_TYPES, ensure_period_quests

        if obj.quest_type in PERIODIC_TYPES:
            result = ensure_period_quests()
            self.message_user(
                request,
                f"Квест будет появляться у студентов каждый период. На сегодня заведено: +{result['created']}.",
            )
            return
        quest_defaults = {
            "title": obj.title,
            "description": obj.description,
            "quest_type": obj.quest_type,
            "reward_coins": obj.reward_coins,
            "reward_rating_delta": 0,
            "conditions": obj.build_conditions(),
            "is_active": obj.is_active,
        }
        _, created = Quest.objects.update_or_create(code=obj.code, defaults=quest_defaults)
        self.message_user(request, "Квест создан и виден студентам." if created else "Квест обновлён.")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and (
            request.user.is_superuser or request.user.role in {"admin", "curator", "tutor", "hq"}
        )


@admin.register(Quest)
class QuestAdmin(ManagedRoleAdminMixin):
    """Квесты, которые видят студенты. Новые заводятся через «Шаблоны квестов»:
    здесь удобно включить или выключить квест и поправить награду."""

    list_display = ("title", "quest_type", "period_key", "reward_coins", "is_active")
    readonly_fields = ("conditions",)
    # Удаление квеста каскадом стирает прогресс студентов, награды и заявки.
    deactivate_instead_of_delete = True
    actions = ("extend_deadline",)

    @admin.action(description="Продлить срок…")
    def extend_deadline(self, request, queryset):
        from apps.operations.admin_actions import action_form

        form, response = action_form(
            self, request, queryset, ExtendDeadlineForm,
            title="Продлить срок квестов",
            intro="Квест без срока получит срок от сегодняшнего дня.",
            submit_label="Продлить",
        )
        if response is not None:
            return response
        days = form.cleaned_data["days"]
        now = timezone.now()
        for quest in queryset:
            quest.end_at = max(quest.end_at or now, now) + timedelta(days=days)
            quest.save(update_fields=["end_at"])
            self.log_change(request, quest, f"Срок продлён на {days} дн.")
        self.message_user(request, f"Продлено квестов: {queryset.count()} — на {days} дн.")
        return None

    def has_add_permission(self, request):
        # Квест без шаблона не знает, как его проверять: новые — через шаблоны.
        return False
    list_filter = ("quest_type", "is_active", "start_at", "end_at")
    search_fields = ("code", "title")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and (request.user.is_superuser or request.user.role in {"admin", "curator", "tutor", "hq"})


@admin.register(UserQuestProgress)
class UserQuestProgressAdmin(FrozenWhileAccrualsOffMixin, ManagedRoleAdminMixin):
    list_display = ("user", "quest", "progress_value", "is_completed", "updated_at")
    list_filter = ("is_completed", "quest__quest_type", "updated_at")
    search_fields = ("user__callsign", "user__username", "quest__code", "quest__title")
    autocomplete_fields = ("user", "quest",)
    list_select_related = ("user", "quest",)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("user", "user__squad", "quest")
        if request.user.is_superuser or request.user.role == "admin":
            return qs
        if is_curator(request.user) and request.user.squad_id:
            return qs.filter(user__squad_id=request.user.squad_id)
        if is_tutor(request.user):
            return qs.filter(user__squad__course__gte=2, user__squad__course__lte=4)
        return qs.none()

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(QuestRewardTransaction)
class QuestRewardTransactionAdmin(ManagedRoleAdminMixin):
    list_display = ("user", "quest", "coins_delta", "rating_delta", "granted_at")
    list_filter = ("granted_at",)
    search_fields = ("user__callsign", "quest__code")
    autocomplete_fields = ("user", "quest", "progress",)
    list_select_related = ("user", "quest",)

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(SeasonalEvent)
class SeasonalEventAdmin(ManagedRoleAdminMixin):
    list_display = ("code", "title", "progress_percent", "is_active", "started_at", "ended_at")
    list_filter = ("is_active", "started_at", "ended_at")
    search_fields = ("code", "title")
    actions = ("activate_season_operation",)

    @admin.action(description="Штаб: активировать сезонную операцию")
    def activate_season_operation(self, request, queryset):
        if not is_hq(request.user) and not is_superadmin(request.user):
            self.message_user(request, "Действие доступно только штабу.", level=messages.ERROR)
            return
        template = queryset.order_by("id").first()
        if not template:
            self.message_user(request, "Выберите шаблон сезонной операции.", level=messages.ERROR)
            return
        seasonal_event = SeasonalEvent.objects.create(
            code=f"{template.code}-run-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            title=template.title,
            description=template.description,
            progress_percent=0,
            is_active=True,
            started_at=timezone.now(),
            ended_at=template.ended_at,
        )
        LogEntry.objects.log_action(
            user_id=request.user.pk,
            content_type_id=ContentType.objects.get_for_model(SeasonalEvent).pk,
            object_id=seasonal_event.pk,
            object_repr=str(seasonal_event),
            action_flag=ADDITION,
            change_message="Активирована сезонная операция из шаблона.",
        )
        self.message_user(request, f"Сезонная операция '{seasonal_event.title}' активирована.", level=messages.SUCCESS)


@admin.register(SquadLeaderboardSnapshot)
class SquadLeaderboardSnapshotAdmin(ManagedRoleAdminMixin):
    list_display = ("squad", "avg_rating", "agents_count", "captured_at")
    list_filter = ("captured_at", "squad")
    search_fields = ("squad__code", "squad__name")
    autocomplete_fields = ("squad",)
    list_select_related = ("squad",)

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)

    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.role in {"admin", "hq"}


@admin.register(SelfReportProof)
class SelfReportProofAdmin(ManagedRoleAdminMixin):
    """Очередь проверки — главный ежедневный экран куратора.

    Раньше одобрение одной заявки занимало четыре шага: галочка, поиск
    действия в выпадающем списке, «Выполнить», перезагрузка. Комментарий
    студента в списке не показывался — каждую заявку приходилось открывать.
    Теперь решение принимается кнопкой прямо в строке.
    """

    list_display = (
        "user",
        "quest_title",
        "comment_short",
        "proof_link",
        "status_badge",
        "decision",
        "created_at",
    )
    list_filter = ("status", "created_at", "quest__quest_type")
    search_fields = ("user__username", "user__email", "comment", "attachment_link")
    autocomplete_fields = ("quest", "user", "quest_progress", "reviewed_by",)
    list_select_related = ("user", "quest", "reviewed_by",)
    readonly_fields = ("created_at", "reviewed_at", "reviewed_by", "proof_link")
    actions = ("approve_proofs", "reject_proofs")

    @admin.display(description="Квест", ordering="quest__title")
    def quest_title(self, obj: SelfReportProof):
        # Название, а не служебный код вида self-report-lab.
        return obj.quest.title if obj.quest_id else "—"

    @admin.display(description="Что сделал студент")
    def comment_short(self, obj: SelfReportProof):
        text = (obj.comment or "").strip()
        if not text:
            return "—"
        return text if len(text) <= 140 else f"{text[:140]}…"

    def get_list_display(self, request):
        can_change = self.has_change_permission(request)

        @admin.display(description="Решение")
        def decision(obj):
            if not can_change or not self.has_change_permission(request, obj):
                return "—"
            return self.decision(obj)

        return tuple(decision if field == "decision" else field for field in super().get_list_display(request))

    @admin.display(description="Решение")
    def decision(self, obj: SelfReportProof):
        """Кнопки внутри формы списка: у неё уже есть CSRF-токен, а нажатие
        перехватывает changelist_view ниже."""
        if obj.status != SelfReportProofStatus.PENDING:
            return "—"
        return format_html(
            '<button type="submit" name="row_approve" value="{}" class="btn btn-sm btn-success mb-1">'
            "Одобрить</button> "
            '<button type="submit" name="row_reject" value="{}" class="btn btn-sm btn-outline-danger mb-1">'
            "Отклонить</button>",
            obj.pk,
            obj.pk,
        )

    def changelist_view(self, request, extra_context=None):
        if request.method == "POST":
            for field, handler in (("row_approve", self.approve_proofs), ("row_reject", self.reject_proofs)):
                pk = request.POST.get(field)
                if pk and pk.isdigit():
                    if not self.has_change_permission(request):
                        raise PermissionDenied
                    queryset = self.get_queryset(request).filter(pk=int(pk))
                    proof = queryset.first()
                    if proof is None or not self.has_change_permission(request, proof):
                        raise PermissionDenied
                    handler(request, queryset)
                    return HttpResponseRedirect(request.get_full_path())
        return super().changelist_view(request, extra_context)

    def has_add_permission(self, request):
        # Заявки создают студенты; сотруднику создавать их незачем.
        return False

    @admin.display(description="Доказательство")
    def proof_link(self, obj: SelfReportProof):
        """Ссылка кликабельна прямо из списка.

        Куратор одобряет пачками; если ради проверки ссылки нужно открывать
        каждую заявку, проверять перестанут вовсе.
        """
        if not obj.attachment_link:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">открыть</a>', obj.attachment_link
        )

    @admin.display(description="Статус")
    def status_badge(self, obj: SelfReportProof):
        if obj.status == SelfReportProofStatus.APPROVED:
            return format_html('<span style="color:#16a34a;font-weight:700;">Одобрен</span>')
        if obj.status == SelfReportProofStatus.REJECTED:
            return format_html('<span style="color:#dc2626;font-weight:700;">Отклонён</span>')
        return format_html('<span style="color:#ca8a04;font-weight:700;">На проверке</span>')

    def has_module_permission(self, request):
        # HQ must not see self-reports
        return super().has_module_permission(request) and not is_hq(request.user)

    def get_queryset(self, request):
        # Правило видимости живёт в одном месте: счётчик на главной и список
        # в админке обязаны показывать одно и то же.
        from apps.operations.services.review_queue import reviewable_proofs

        allowed = reviewable_proofs(request.user).values("pk")
        return (
            super()
            .get_queryset(request)
            .filter(pk__in=allowed)
            .select_related("user", "user__squad", "quest", "quest_progress")
        )

    @admin.action(description="Одобрить: начислить награду за квест")
    def approve_proofs(self, request, queryset):
        from apps.operations.admin_actions import refuse_while_accruals_off

        # Одобрение сразу начисляет награду, а статус «одобрено» нельзя
        # откатить: до запуска заявки остаются на проверке.
        if refuse_while_accruals_off(self, request):
            return
        if is_hq(request.user):
            self.message_user(request, "Штаб не проверяет подтверждения.", level=messages.ERROR)
            return
        now = timezone.now()
        updated = 0
        for proof in queryset.select_related("quest", "user", "quest_progress"):
            if proof.status == SelfReportProofStatus.APPROVED:
                continue
            # Сначала награда, потом статус: если начисление не прошло, заявка
            # остаётся на проверке, а не «одобрена без награды».
            with transaction.atomic():
                _complete_quest_idempotent(proof.user, proof.quest, request.user)
                proof.status = SelfReportProofStatus.APPROVED
                proof.reviewed_by = request.user
                proof.reviewed_at = now
                proof.save(update_fields=["status", "reviewed_by", "reviewed_at"])
            events.proof_reviewed(proof, approved=True)
            updated += 1
        self.message_user(request, f"Одобрено: {updated}", level=messages.SUCCESS)

    @admin.action(description="Отклонить: награда не начисляется")
    def reject_proofs(self, request, queryset):
        if is_hq(request.user):
            self.message_user(request, "Штаб не проверяет подтверждения.", level=messages.ERROR)
            return
        now = timezone.now()
        rejected = list(
            queryset.exclude(status=SelfReportProofStatus.REJECTED).select_related("user", "quest")
        )
        updated = queryset.exclude(status=SelfReportProofStatus.REJECTED).update(
            status=SelfReportProofStatus.REJECTED, reviewed_by=request.user, reviewed_at=now
        )
        for proof in rejected:
            events.proof_reviewed(proof, approved=False)
        self.message_user(request, f"Отклонено: {updated}", level=messages.SUCCESS)


@admin.register(WeeklyFocus)
class WeeklyFocusAdmin(ManagedRoleAdminMixin):
    """Какой квест студент выбрал целью недели (за него идёт надбавка)."""

    list_display = ("user", "quest", "period_key", "updated_at")
    list_filter = ("period_key",)
    search_fields = ("user__username", "user__callsign", "user__last_name", "quest__title")
    list_select_related = ("user", "quest")
    autocomplete_fields = ("user", "quest")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)
