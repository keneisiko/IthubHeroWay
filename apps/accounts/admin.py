from __future__ import annotations

import hashlib
from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import slugify

from apps.operations.admin_actions import action_form
from apps.operations.admin_rbac import (
    ManagedRoleAdminMixin,
    is_admin,
    is_curator,
    is_hq,
    is_superadmin,
    is_tutor,
)
from apps.progress.services.polozhenie_awards import (
    UnknownTariff,
    award_bulk_by_tariff_code,
    tariff_choices,
)
from apps.progress.services.rating_zones import ZONE_COLORS, ZONE_NAMES_RU
from apps.progress.services.rating_zones import rating_zone as zone_of
from apps.quests.models import Quest, QuestType, UserQuestProgress

from .models import PolicyAcceptance, Role, Squad, Track, User


def _grouped_tariff_choices():
    """Тарифы разделов 5–7 сгруппированы: мероприятия, олимпиады, проекты.

    Плоский список из двух десятков строк «Мероприятие — Слушатель, Колледж
    (1 / 3)» новичку читать тяжело; группы в выпадающем списке — легко.
    Суммы берутся из настроек Положения, без дублирования.
    """
    groups: dict[str, list[tuple[str, str]]] = {}
    for code, label in tariff_choices():
        group, _, rest = label.partition(" — ")
        groups.setdefault(group, []).append((code, rest or label))
    return [("", "— выберите —")] + [(group, items) for group, items in groups.items()]


class PolozhenieAwardForm(forms.Form):
    tariff_code = forms.ChoiceField(
        label="Что засчитываем",
        choices=_grouped_tariff_choices,
        help_text="В скобках — сколько получит каждый студент: рейтинг / монеты.",
    )
    activity_title = forms.CharField(
        label="Название мероприятия",
        max_length=200,
        help_text="Как оно будет называться в истории студента, например «Хакатон IThub 2026».",
    )
    activity_date = forms.DateField(
        label="Дата мероприятия",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Одно мероприятие в один день засчитывается студенту один раз, даже если нажать дважды.",
    )
    note = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Необязательно. Видно в журнале начислений.",
    )


class RecoveryQuestForm(forms.Form):
    days = forms.IntegerField(
        label="Сколько дней на квест",
        min_value=3,
        max_value=7,
        initial=5,
        help_text="От 3 до 7 дней.",
    )


def activity_key_for(title: str, day) -> str:
    """Ключ мероприятия, по которому нельзя заплатить дважды.

    Раньше ключ был `slugify(title)` — а он без allow_unicode выбрасывает
    кириллицу целиком: «Олимпиада по математике» и «Субботник» давали одну
    и ту же пустую строку. Второе мероприятие того же дня считалось уже
    оплаченным, и студенты его молча не получали. Хеш полного названия
    различает и мероприятия, чьи названия совпадают в начале.
    """
    slug = slugify(title, allow_unicode=True)[:28] or "activity"
    digest = hashlib.sha1(title.strip().lower().encode("utf-8")).hexdigest()[:6]
    return f"{slug}-{digest}:{day.isoformat()}"


@admin.register(Track)
class TrackAdmin(ManagedRoleAdminMixin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(Squad)
class SquadAdmin(ManagedRoleAdminMixin):
    list_display = ("code", "name", "course", "capacity")
    list_filter = ("course",)
    search_fields = ("code", "name")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if is_curator(request.user) and request.user.squad_id:
            return qs.filter(pk=request.user.squad_id)
        return qs


@admin.register(User)
class UserAdmin(ManagedRoleAdminMixin, BaseUserAdmin):
    list_display = (
        "username",
        "callsign",
        "role",
        "squad",
        "rating_zone",
        "rating_current",
        "coins_balance",
        "is_active",
    )
    list_filter = ("role", "squad", "is_active", "date_joined")
    search_fields = ("username", "callsign", "first_name", "last_name", "email", "hik_card_code")
    autocomplete_fields = ("squad", "track",)
    list_select_related = ("squad", "track",)
    ordering = ("-rating_current", "username")
    actions = ("grant_polozhenie_award", "create_recovery_quest")
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Путь героя",
            {
                "fields": (
                    "callsign",
                    "avatar",
                    "track",
                    "squad",
                    "role",
                    "coins_balance",
                    "status",
                    "level",
                    "rating_current",
                    "unclosed_ct_count",
                    "lxp_user_id",
                    "hik_card_code",
                    "hik_person_id",
                )
            },
        ),
    )

    @admin.display(description="Зона")
    def rating_zone(self, obj: User) -> str:
        # Пороги берутся из rating_zones, а не дублируются здесь: раньше
        # админка, дашборды и API считали зоны по трём независимым копиям.
        code = zone_of(obj.rating_current)
        return format_html(
            '<span style="color:{};font-weight:700;">{}</span>',
            ZONE_COLORS.get(code, "#000000"),
            ZONE_NAMES_RU.get(code, code),
        )

    def has_module_permission(self, request):
        if is_hq(request.user):
            return False
        return super().has_module_permission(request)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("squad", "track")
        if is_superadmin(request.user) or is_admin(request.user):
            return qs
        if is_curator(request.user):
            if request.user.squad_id:
                return qs.filter(squad_id=request.user.squad_id)
            return qs.none()
        if is_tutor(request.user):
            return qs.filter(squad__course__gte=2, squad__course__lte=4)
        return qs.none()

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if is_admin(request.user) and not is_superadmin(request.user):
            readonly.extend(["is_superuser", "user_permissions", "groups"])
        if is_curator(request.user) or is_tutor(request.user):
            readonly.extend(["is_superuser", "is_staff", "user_permissions", "groups", "role"])
        return readonly

    def save_model(self, request, obj, form, change):
        # Admin cannot create/upgrade superusers.
        if is_admin(request.user) and not is_superadmin(request.user):
            obj.is_superuser = False
        super().save_model(request, obj, form, change)

    def get_actions(self, request):
        """Показывать только действия, доступные роли.

        Раньше админ видел «создать восстановительный квест», нажимал — и
        получал «доступно только тьютору». Недоступное лучше не показывать.
        """
        actions = super().get_actions(request)
        user = request.user
        if not (is_superadmin(user) or is_admin(user) or is_tutor(user) or is_hq(user)):
            actions.pop("grant_polozhenie_award", None)
        if not (is_superadmin(user) or is_tutor(user)):
            actions.pop("create_recovery_quest", None)
        return actions

    @admin.action(description="Начислить по Положению: мероприятие, олимпиада, проект…")
    def grant_polozhenie_award(self, request, queryset):
        """Пакетное начисление по разделам 5–7 Положения.

        Положение (п. 5.1) допускает подтверждение участия списком: выбрать
        студентов, тариф и назвать мероприятие. Раньше рядом стояло действие
        «+10 монет за мероприятие» — мимо Положения, без рейтинга и записи
        в журнал начислений; новичок выбирал его как более простое.
        """
        agents = queryset.filter(role=Role.AGENT)
        skipped = queryset.count() - agents.count()
        form, response = action_form(
            self,
            request,
            agents,
            PolozhenieAwardForm,
            title="Начисление по Положению",
            intro="Выберите, что засчитываете, и назовите мероприятие. Начисление попадёт "
            "в журнал рейтинга каждого студента с вашим именем.",
            submit_label="Начислить",
            skipped_note=f"Не студентов в выборке: {skipped} — им ничего не начислится." if skipped else "",
        )
        if response is not None:
            return response

        data = form.cleaned_data
        title = data["activity_title"].strip()
        note = (data.get("note") or "").strip()
        students = list(agents)
        try:
            result = award_bulk_by_tariff_code(
                students,
                data["tariff_code"],
                activity_key=activity_key_for(title, data["activity_date"]),
                title=title,
                happened_on=data["activity_date"],
                confirmed_by=request.user,
                note=note,
            )
        except UnknownTariff as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return None

        for user in students:
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=ContentType.objects.get_for_model(User).pk,
                object_id=user.pk,
                object_repr=str(user),
                action_flag=CHANGE,
                change_message=f"{data['tariff_code']} «{title}». {note}".strip(),
            )

        self.message_user(
            request,
            f"«{title}»: начислено {result['granted']} студентам "
            f"(+{result['rating']} рейтинга, +{result['coins']} монет). "
            f"Уже получали это мероприятие раньше: {result['skipped']}.",
            level=messages.SUCCESS,
        )
        return None

    @admin.action(description="Создать восстановительный квест…")
    def create_recovery_quest(self, request, queryset):
        targets = queryset.filter(squad__course__gte=2, squad__course__lte=4)
        skipped = queryset.count() - targets.count()
        form, response = action_form(
            self,
            request,
            targets,
            RecoveryQuestForm,
            title="Восстановительный квест",
            intro="Индивидуальный квест для студентов, которым нужно подтянуть рейтинг.",
            submit_label="Создать квест",
            skipped_note=f"Не 2–4 курс: {skipped} — им квест не создастся." if skipped else "",
        )
        if response is not None:
            return response

        days = form.cleaned_data["days"]
        now = timezone.now()
        created = 0
        # Квест создаётся внутри транзакции: раньше он писался до atomic(), и при
        # ошибке на создании прогресса в базе оставался квест без участников.
        with transaction.atomic():
            quest = Quest.objects.create(
                code=f"recovery-{now.strftime('%Y%m%d%H%M%S')}",
                title="Восстановительный квест",
                description="Индивидуальный восстановительный квест для улучшения рейтинга.",
                quest_type=QuestType.LONG,
                reward_coins=5,
                # Квесты дают только монеты: рейтинг начисляется по Положению
                # (разделы 3–7). Прежние +15 рейтинга шли в обход него.
                reward_rating_delta=0,
                is_active=True,
                start_at=now,
                end_at=now + timedelta(days=days),
                conditions={"type": "recovery", "created_by": request.user.username},
            )
            for user in targets:
                _, was_created = UserQuestProgress.objects.get_or_create(user=user, quest=quest)
                created += int(was_created)
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=ContentType.objects.get_for_model(Quest).pk,
                object_id=quest.pk,
                object_repr=str(quest),
                action_flag=ADDITION,
                change_message=f"Создан восстановительный квест для {created} студентов.",
            )
        self.message_user(request, f"Создан восстановительный квест на {days} дн. для {created} студентов.")
        return None


@admin.register(PolicyAcceptance)
class PolicyAcceptanceAdmin(ManagedRoleAdminMixin):
    """Кто и когда принял Положение.

    Запись — юридический факт согласия, поэтому только просмотр: создаёт её
    сам студент, а правка задним числом лишила бы её смысла.
    """

    list_display = ("user", "version", "accepted_at")
    list_filter = ("version", "accepted_at", "user__squad")
    search_fields = ("user__username", "user__callsign", "user__last_name")
    list_select_related = ("user",)
    date_hierarchy = "accepted_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
