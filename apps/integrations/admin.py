from django.contrib import admin, messages

from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq

from .models import ExternalEvent, HikEvent, HikSnapshot, LXPSnapshot


class ExternalEventTypeFilter(admin.SimpleListFilter):
    title = "Тип события"
    parameter_name = "event_type"

    def lookups(self, request, model_admin):
        return (
            ("late", "Опоздание"),
            ("access", "Проход"),
            ("absent", "Прогул"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        return queryset.filter(payload__event_type=value)


@admin.register(ExternalEvent)
class ExternalEventAdmin(ManagedRoleAdminMixin):
    list_display = ("source", "external_event_id", "event_type_display", "processed_at")
    list_filter = ("source", ExternalEventTypeFilter, "processed_at")
    search_fields = ("external_event_id", "source")
    readonly_fields = ("source", "external_event_id", "payload", "processed_at")

    @admin.display(description="Тип")
    def event_type_display(self, obj: ExternalEvent) -> str:
        return (obj.payload or {}).get("event_type") or "—"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


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


@admin.register(HikSnapshot)
class HikSnapshotAdmin(ManagedRoleAdminMixin):
    list_display = ("date", "events_count", "source_display", "created_at")
    readonly_fields = ("date", "data", "created_at")
    actions = ("apply_snapshot",)

    @admin.display(description="Событий")
    def events_count(self, obj: HikSnapshot) -> int:
        data = obj.data or {}
        meta = data.get("meta") or {}
        if meta.get("events_count") is not None:
            return int(meta["events_count"])
        events = data.get("events")
        return len(events) if isinstance(events, list) else 0

    @admin.display(description="Источник")
    def source_display(self, obj: HikSnapshot) -> str:
        return str((obj.data or {}).get("meta", {}).get("source") or "—")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.role == "admin"

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)

    @admin.action(description="Импортировать снимок → HikEvent → ExternalEvent")
    def apply_snapshot(self, request, queryset):
        from apps.integrations.services.hik_snapshot_service import apply_hik_snapshot

        done = 0
        for snap in queryset:
            apply_hik_snapshot(snap.date, skip_process=False)
            done += 1
        self.message_user(request, f"Обработано снимков Hik: {done}.", level=messages.SUCCESS)


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
