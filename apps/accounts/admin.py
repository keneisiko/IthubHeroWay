from __future__ import annotations

from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django.utils.html import format_html

from apps.operations.admin_rbac import (
    ManagedRoleAdminMixin,
    is_admin,
    is_curator,
    is_hq,
    is_superadmin,
    is_tutor,
)
from apps.progress.services.drive_awards import UnknownDriveCode, grant_drive_award_bulk
from apps.progress.services.drive_awards import available_codes as available_drive_codes
from apps.progress.services.rating_zones import ZONE_COLORS, ZONE_NAMES_RU
from apps.progress.services.rating_zones import rating_zone as zone_of
from apps.progress.services.rewards import grant_coins_with_daily_cap
from apps.quests.models import Quest, QuestType, UserQuestProgress

from .models import Role, Squad, Track, User


def _drive_choices():
    """Коды «Движа» с их стоимостью — прямо из настроек, без дублирования."""
    return [(code, f"{code} (+{points})") for code, points in sorted(available_drive_codes().items())]


class UserAdminActionForm(ActionForm):
    reason = forms.CharField(required=False, label="Причина")
    recovery_days = forms.IntegerField(required=False, min_value=3, max_value=7, initial=5, label="Дней квеста")
    drive_code = forms.ChoiceField(required=False, choices=_drive_choices, label="Тип активности")


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
    action_form = UserAdminActionForm
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
    ordering = ("-rating_current", "username")
    actions = ("grant_event_bonus", "create_recovery_quest", "grant_drive_award")
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

    @admin.action(description="Куратор: начислить +10 монет за мероприятие")
    def grant_event_bonus(self, request, queryset):
        if not is_curator(request.user):
            self.message_user(request, "Действие доступно только куратору.", level=messages.ERROR)
            return
        reason = request.POST.get("reason", "").strip() or "Бонус за участие в мероприятии"
        # Фильтр по роли обязателен: без него куратор мог начислить монеты
        # любому пользователю своего отряда, включая staff-аккаунты.
        queryset = queryset.filter(squad_id=request.user.squad_id, role=Role.AGENT)
        with transaction.atomic():
            updated = 0
            for user in queryset:
                granted = grant_coins_with_daily_cap(user, 10)
                if not granted:
                    continue
                LogEntry.objects.log_action(
                    user_id=request.user.pk,
                    content_type_id=ContentType.objects.get_for_model(User).pk,
                    object_id=user.pk,
                    object_repr=str(user),
                    action_flag=CHANGE,
                    change_message=f"Начислено +10 монет. Причина: {reason}",
                )
                updated += 1
        self.message_user(request, f"Начислено +10 монет для {updated} студентов.", level=messages.SUCCESS)

    @admin.action(description="Начислить рейтинг за активность («Движ»)")
    def grant_drive_award(self, request, queryset):
        """Единственная точка, где начисляются коэффициенты RATING_DRIVE.

        Раньше блок «Движ» не был подключён нигде: мероприятия, олимпиады и
        проекты на рейтинг не влияли вообще.
        """
        if not (is_tutor(request.user) or is_hq(request.user) or is_admin(request.user)):
            self.message_user(
                request,
                "Действие доступно тьютору, штабу и администратору.",
                level=messages.ERROR,
            )
            return

        code = (request.POST.get("drive_code") or "").strip()
        if not code:
            self.message_user(request, "Выберите тип активности.", level=messages.ERROR)
            return

        note = (request.POST.get("reason") or "").strip()
        agents = queryset.filter(role=Role.AGENT)
        try:
            result = grant_drive_award_bulk(agents, code, note=note)
        except UnknownDriveCode as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return

        for user in agents:
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=ContentType.objects.get_for_model(User).pk,
                object_id=user.pk,
                object_repr=str(user),
                action_flag=CHANGE,
                change_message=f"Движ {code}: +{result.points_each} рейтинга. {note}".strip(),
            )

        self.message_user(
            request,
            f"«{code}»: начислено {result.granted} студентам по +{result.points_each}; "
            f"повторно за сегодня пропущено {result.skipped_duplicate}.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Тьютор: создать восстановительный квест (3-7 дней)")
    def create_recovery_quest(self, request, queryset):
        if not is_tutor(request.user):
            self.message_user(request, "Действие доступно только тьютору.", level=messages.ERROR)
            return
        # Нечисловое значение в поле формы раньше валило действие с 500:
        # int() поднимал ValueError прямо в admin-вьюхе.
        try:
            days = int(request.POST.get("recovery_days") or 5)
        except (TypeError, ValueError):
            self.message_user(request, "Поле «Дней квеста» должно быть числом от 3 до 7.", level=messages.ERROR)
            return
        days = min(max(days, 3), 7)
        now = timezone.now()
        quest_code = f"recovery-{now.strftime('%Y%m%d%H%M%S')}"
        target_users = queryset.filter(squad__course__gte=2, squad__course__lte=4)
        created = 0
        # Квест создаётся внутри транзакции: раньше он писался до atomic(), и при
        # ошибке на создании прогресса в базе оставался квест без участников.
        with transaction.atomic():
            quest = Quest.objects.create(
                code=quest_code,
                title="Восстановительный квест",
                description="Индивидуальный восстановительный квест для улучшения рейтинга.",
                quest_type=QuestType.LONG,
                reward_coins=5,
                reward_rating_delta=15,
                is_active=True,
                start_at=now,
                end_at=now + timedelta(days=days),
                conditions={"type": "recovery", "created_by": request.user.username},
            )
            for user in target_users:
                _, was_created = UserQuestProgress.objects.get_or_create(user=user, quest=quest)
                if was_created:
                    created += 1
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=ContentType.objects.get_for_model(Quest).pk,
                object_id=quest.pk,
                object_repr=str(quest),
                action_flag=ADDITION,
                change_message=f"Создан восстановительный квест для {created} студентов.",
            )
        self.message_user(request, f"Создан восстановительный квест для {created} студентов.", level=messages.SUCCESS)
