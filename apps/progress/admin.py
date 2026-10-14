from django.contrib import admin

from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq

from .models import (
    Characteristic,
    CharacteristicHistory,
    PolozhenieAward,
    RatingLog,
    StudentRoleAssignment,
    UserStrike,
)


@admin.register(RatingLog)
class RatingLogAdmin(ManagedRoleAdminMixin):
    # Монеты, период и подтвердивший показаны в списке: п. 10.1 Положения
    # требует, чтобы по записи было видно основание, период и ответственного.
    list_display = (
        "user",
        "delta",
        "coins_delta",
        "source",
        "period_key",
        "confirmed_by",
        "reason",
        "created_at",
    )
    list_filter = ("source", "period_key", "created_at")
    search_fields = ("user__callsign", "user__username", "reason", "source_id")
    autocomplete_fields = ("user", "confirmed_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(Characteristic)
class CharacteristicAdmin(ManagedRoleAdminMixin):
    list_display = ("user", "pillar", "current", "peak", "last_updated")
    list_filter = ("pillar", "last_updated")
    search_fields = ("user__callsign", "user__username", "pillar")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(CharacteristicHistory)
class CharacteristicHistoryAdmin(ManagedRoleAdminMixin):
    list_display = ("characteristic", "value", "formula_version", "created_at")
    list_filter = ("formula_version", "created_at")
    search_fields = ("characteristic__user__callsign", "characteristic__pillar")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(UserStrike)
class UserStrikeAdmin(ManagedRoleAdminMixin):
    list_display = (
        "user",
        "attendance_strike",
        "late_strike",
        "last_attendance_date",
        "last_late_date",
        "updated_at",
    )
    search_fields = ("user__callsign", "user__username")
    readonly_fields = ("updated_at",)

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(StudentRoleAssignment)
class StudentRoleAssignmentAdmin(ManagedRoleAdminMixin):
    """Раздел 4 Положения: ответственный фиксирует начало и окончание статуса."""

    list_display = ("user", "kind", "started_on", "ended_on", "confirmed_by", "note")
    list_filter = ("kind", "started_on", "ended_on")
    search_fields = ("user__callsign", "user__username", "note")
    autocomplete_fields = ("user", "confirmed_by")

    def save_model(self, request, obj, form, change):
        # Подтвердивший подставляется сам: Положение требует указать
        # ответственного, а забыть выбрать его из списка слишком легко.
        if not obj.confirmed_by_id:
            obj.confirmed_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PolozhenieAward)
class PolozhenieAwardAdmin(ManagedRoleAdminMixin):
    """Разделы 5-7: подтверждённые мероприятия, олимпиады и проекты."""

    list_display = (
        "user",
        "kind",
        "activity_key",
        "title",
        "level",
        "role",
        "happened_on",
        "rating_granted",
        "coins_granted",
        "confirmed_by",
    )
    list_filter = ("kind", "level", "role", "happened_on")
    search_fields = ("user__callsign", "user__username", "activity_key", "title")
    autocomplete_fields = ("user", "confirmed_by")
    readonly_fields = ("rating_granted", "coins_granted", "created_at")

    def has_add_permission(self, request):
        # Начисление заводится командой `award_polozhenie`, а не вручную:
        # иначе запись появится без самого начисления рейтинга и монет.
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
