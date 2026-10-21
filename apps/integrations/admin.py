from django.contrib import admin, messages

from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq

from .models import ExternalEvent, HikEvent, HikImportRun, HikSnapshot, LXPSnapshot, TelegramAccountLink


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
    list_display = ("event_time", "student_code", "event_type", "door_name", "processed", "unmatched")
    list_filter = ("processed", "unmatched")
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
        queryset.update(processed=False, unmatched=False)
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
        # В фоне: в запросе обработка до 50 000 событий упиралась в таймаут
        # gunicorn, и страница падала с 502 посреди работы.
        from apps.integrations.tasks import apply_hik_snapshot_task

        dates = sorted({snap.date for snap in queryset})
        for day in dates:
            apply_hik_snapshot_task.delay(day.isoformat())
        self.message_user(
            request,
            f"Запущена обработка снимков Hik: {len(dates)}. Это займёт несколько минут — "
            "результат появится в «Запусках импорта Hik» и в посещаемости.",
            level=messages.SUCCESS,
        )


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


@admin.register(HikImportRun)
class HikImportRunAdmin(ManagedRoleAdminMixin):
    """Журнал импортов: по нему видно, работает интеграция или молчит."""

    list_display = (
        "started_at",
        "mode",
        "status",
        "date_from",
        "date_to",
        "records_fetched",
        "events_created",
        "external_created",
        "users_unmatched",
        "relogin_used",
        "duration_ms",
    )
    list_filter = ("status", "mode", "started_at")
    readonly_fields = tuple(f.name for f in HikImportRun._meta.fields)
    ordering = ("-started_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(TelegramAccountLink)
class TelegramAccountLinkAdmin(ManagedRoleAdminMixin):
    """Кто из студентов привязал Telegram.

    Раньше этого экрана не было: на вопрос «почему я не вижу себя в отряде»
    (видимость в отряде зависит от активной привязки) ответить можно было
    только из базы. Идентификаторы Telegram руками не правятся — их пишет
    бот при /activate; персонал может только отвязать.
    """

    list_display = ("user", "telegram_username", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("user__username", "user__callsign", "user__last_name", "telegram_username")
    list_select_related = ("user",)
    readonly_fields = ("user", "telegram_user_id", "telegram_chat_id", "telegram_username", "created_at", "updated_at")
    actions = ("unlink",)
    bulk_active_actions = False

    def has_add_permission(self, request):
        return False

    @admin.action(description="Отвязать Telegram (студент сможет привязать заново)", permissions=("delete",))
    def unlink(self, request, queryset):
        # Удаление, а не is_active=False: сменивший телефон студент иначе
        # упирался бы в «этот Telegram уже привязан» на новом аккаунте.
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"Отвязано: {count}. Студенты могут снова отправить боту /activate.")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)
