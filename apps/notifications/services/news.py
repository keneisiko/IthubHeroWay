"""Публикация новостей и рассылка в Telegram-бот."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.integrations.models import TelegramAccountLink
from apps.notifications.models import News
from apps.notifications.services.telegram import notify_users


def site_url(path: str) -> str:
    base = getattr(settings, "FRONTEND_URL", "") or "https://hero.ithub-nalchik.ru"
    return f"{base.rstrip('/')}{path}" if path.startswith("/") else path


def telegram_text(news: News) -> str:
    text = f"📰 {news.title}\n\n{news.body}"
    if news.link:
        text += f"\n\n{site_url(news.link)}"
    return text


def linked_users():
    ids = TelegramAccountLink.objects.filter(is_active=True).values_list("user_id", flat=True)
    return User.objects.filter(pk__in=ids)


def publish(news: News, *, send_to_telegram: bool) -> int:
    """Опубликовать новость; вернуть, скольким отправлено в бот.

    Повторно в бот новость не уходит: второе нажатие не заспамит студентов.
    """
    with transaction.atomic():
        locked = News.objects.select_for_update().get(pk=news.pk)
        if not locked.is_published:
            locked.is_published = True
            locked.published_at = timezone.now()
        should_send = send_to_telegram and locked.sent_to_telegram_at is None
        if should_send:
            locked.sent_to_telegram_at = timezone.now()
        locked.save(update_fields=["is_published", "published_at", "sent_to_telegram_at"])
    if not should_send:
        return 0
    return notify_users(linked_users(), telegram_text(locked))
