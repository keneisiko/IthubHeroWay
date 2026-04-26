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
from apps.quests.models import Quest, QuestType, SeasonalEvent, UserQuestProgress

from .models import Role, Squad, Track, User


class UserAdminActionForm(ActionForm):
    reason = forms.CharField(required=False, label="Причина")
    recovery_days = forms.IntegerField(required=False, min_value=3, max_value=7, initial=5, label="Дней квеста")


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
    search_fields = ("username", "callsign", "first_name", "last_name", "email")
    ordering = ("-rating_current", "username")
    actions = ("grant_event_bonus", "create_recovery_quest")
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Hero Path",
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
                )
            },
        ),
    )

    @admin.display(description="Зона")
    def rating_zone(self, obj: User) -> str:
        rating = obj.rating_current
        if rating < 100:
            return format_html('<span style="color:#d32f2f;font-weight:700;">Красная</span>')
        if rating < 200:
            return format_html('<span style="color:#ef6c00;font-weight:700;">Оранжевая</span>')
        if rating < 400:
            return format_html('<span style="color:#f9a825;font-weight:700;">Желтая</span>')
        if rating < 650:
            return format_html('<span style="color:#2e7d32;font-weight:700;">Зеленая</span>')
        if rating < 850:
            return format_html('<span style="color:#1976d2;font-weight:700;">Платиновая</span>')
        return format_html('<span style="color:#6a1b9a;font-weight:700;">Золотая</span>')

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
        reason = request.POST.get("reason", "").strip() or "Bonus for event participation"
        queryset = queryset.filter(squad_id=request.user.squad_id)
        with transaction.atomic():
            updated = 0
            for user in queryset:
                user.coins_balance += 10
                user.save(update_fields=["coins_balance"])
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

    @admin.action(description="Тьютор: создать восстановительный квест (3-7 дней)")
    def create_recovery_quest(self, request, queryset):
        if not is_tutor(request.user):
            self.message_user(request, "Действие доступно только тьютору.", level=messages.ERROR)
            return
        days = int(request.POST.get("recovery_days") or 5)
        days = min(max(days, 3), 7)
        now = timezone.now()
        quest_code = f"recovery-{now.strftime('%Y%m%d%H%M%S')}"
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
        target_users = queryset.filter(squad__course__gte=2, squad__course__lte=4)
        created = 0
        with transaction.atomic():
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
