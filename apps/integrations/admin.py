from django.contrib import admin, messages

from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq

from .models import HikEvent, LXPSnapshot


@admin.register(HikEvent)
class HikEventAdmin(ManagedRoleAdminMixin):
    list_display = ("event_time", "student_code", "event_type", "door_name", "processed")
    list_filter = ("processed",)
    search_fields = ("event_id", "student_code", "door_name")
    readonly_fields = (
        "event_id",
        "student_code",
        "event_time",
        "event_type",
        "door_name",
        "raw_data",
        "processed",
        "created_at",
    )
    actions = ("mark_unprocessed",)

    def has_add_permission(self, request):
        return False

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)

    @admin.action(description="Снять признак «обработано» (повторная обработка)")
    def mark_unprocessed(self, request, queryset):
        queryset.update(processed=False)
        self.message_user(request, f"Снят признак «обработано» для {queryset.count()} записей.", level=messages.WARNING)


@admin.register(LXPSnapshot)
class LXPSnapshotAdmin(ManagedRoleAdminMixin):
    list_display = ("date", "created_at")
    readonly_fields = ("date", "data", "created_at")
    actions = ("apply_snapshot",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == "admin"

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)

    @admin.action(description="Применить снимок вручную (пересчитать рейтинг)")
    def apply_snapshot(self, request, queryset):
        from apps.progress.tasks import recalculate_rating_for_date

        for snap in queryset:
            recalculate_rating_for_date.delay(snap.date.isoformat())
        self.message_user(request, f"Запущен пересчёт для {queryset.count()} снимков.", level=messages.SUCCESS)

