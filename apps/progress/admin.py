from django.contrib import admin

from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq

from .models import (
    Characteristic,
    CharacteristicHistory,
    CourseTopicNorm,
    LessonAttendance,
    LXPTopicState,
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
    list_select_related = ("user", "confirmed_by",)
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
    autocomplete_fields = ("user",)
    list_select_related = ("user",)

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(CharacteristicHistory)
class CharacteristicHistoryAdmin(ManagedRoleAdminMixin):
    list_display = ("characteristic", "value", "formula_version", "created_at")
    list_filter = ("formula_version", "created_at")
    search_fields = ("characteristic__user__callsign", "characteristic__pillar")
    autocomplete_fields = ("characteristic",)
    list_select_related = ("characteristic__user",)

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
    autocomplete_fields = ("user",)
    list_select_related = ("user",)
    readonly_fields = ("updated_at",)

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(StudentRoleAssignment)
class StudentRoleAssignmentAdmin(ManagedRoleAdminMixin):
    """Раздел 4 Положения: ответственный фиксирует начало и окончание статуса."""

    list_display = ("user", "kind", "started_on", "ended_on", "confirmed_by", "note")
    list_filter = ("kind", "started_on", "ended_on")
    search_fields = ("user__callsign", "user__username", "note")
    list_select_related = ("user", "confirmed_by",)
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
    list_select_related = ("user", "confirmed_by",)
    autocomplete_fields = ("user", "confirmed_by")
    readonly_fields = ("rating_granted", "coins_granted", "created_at")

    def has_add_permission(self, request):
        # Начисление заводится командой `award_polozhenie`, а не вручную:
        # иначе запись появится без самого начисления рейтинга и монет.
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser


class _ReadOnlyFromIntegration(ManagedRoleAdminMixin):
    """Данные, которые каждую ночь перезаписывает интеграция.

    Правка руками здесь бессмысленна и вредна: ночная загрузка молча вернула
    бы старое значение, и персонал считал бы, что исправил, а исправления
    нет. Поэтому экран только для просмотра — исправлять надо в источнике.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(LessonAttendance)
class LessonAttendanceAdmin(_ReadOnlyFromIntegration):
    """Отметки посещения пар из LXP. Исправлять — в журнале LXP."""

    list_display = ("user", "lesson_date", "starts_at", "discipline", "status", "updated_at")
    list_filter = ("status", "lesson_date", "user__squad")
    search_fields = ("user__username", "user__callsign", "user__last_name", "discipline")
    list_select_related = ("user",)
    date_hierarchy = "lesson_date"
    ordering = ("-lesson_date", "-starts_at")


@admin.register(LXPTopicState)
class LXPTopicStateAdmin(_ReadOnlyFromIntegration):
    """Последнее известное состояние тем студента по снимку LXP."""

    list_display = ("user", "last_snapshot_date", "baseline_done", "updated_at")
    list_filter = ("baseline_done", "last_snapshot_date")
    search_fields = ("user__username", "user__callsign", "user__last_name")
    list_select_related = ("user",)


@admin.register(CourseTopicNorm)
class CourseTopicNormAdmin(ManagedRoleAdminMixin):
    """Сколько тем ожидается на курсе. Это настройка, её правит персонал."""

    list_display = ("course", "expected_topics", "updated_at")
    ordering = ("course",)

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)
