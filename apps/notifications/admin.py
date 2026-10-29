from django.contrib import admin, messages

from apps.operations.admin_rbac import ManagedRoleAdminMixin

from .models import News
from .services.news import publish


@admin.register(News)
class NewsAdmin(ManagedRoleAdminMixin):
    list_display = ("title", "is_published", "published_at", "sent_to_telegram_at")
    list_filter = ("is_published",)
    search_fields = ("title", "body")
    fields = ("title", "body", "link", "is_published", "published_at", "sent_to_telegram_at", "created_by")
    readonly_fields = ("is_published", "published_at", "sent_to_telegram_at", "created_by")
    actions = ("publish_and_send", "publish_only", "unpublish")

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Опубликовать и отправить в бот")
    def publish_and_send(self, request, queryset):
        sent = sum(publish(news, send_to_telegram=True) for news in queryset)
        self.message_user(request, f"Опубликовано: {queryset.count()}, сообщений в бот: {sent}.", messages.SUCCESS)

    @admin.action(description="Опубликовать без рассылки")
    def publish_only(self, request, queryset):
        for news in queryset:
            publish(news, send_to_telegram=False)
        self.message_user(request, f"Опубликовано: {queryset.count()}.", messages.SUCCESS)

    @admin.action(description="Снять с главной")
    def unpublish(self, request, queryset):
        queryset.update(is_published=False)
        self.message_user(request, "Новости сняты с главной.", messages.SUCCESS)
