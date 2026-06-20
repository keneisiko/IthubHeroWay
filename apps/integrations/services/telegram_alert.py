"""Централизованные Telegram-оповещения об ошибках с дедупликацией."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.integrations.services.telegram_notify import send_admin_alert

logger = logging.getLogger(__name__)

_EMOJI_MAP = {
    "auth": "🔑",
    "api": "🌐",
    "db": "🗄️",
    "celery": "🧵",
    "rating": "📊",
    "lxp": "📚",
    "hik": "🚪",
    "critical": "🚨",
    "warning": "⚠️",
    "info": "ℹ️",
    "error": "❌",
}


def format_alert_message(title: str, message: str, error_type: str) -> str:
    emoji = _EMOJI_MAP.get(error_type, "❌")
    ts = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S")
    env = getattr(settings, "ENVIRONMENT_NAME", "development")
    body = (message or "").strip()
    if len(body) > 3200:
        body = body[:3200] + "\n...(truncated)"
    return (
        f"{emoji} {title}\n\n"
        f"📅 {ts}\n\n"
        f"📝 Детали:\n{body}\n\n"
        f"🔧 Среда: {env}"
    )


def send_alert_to_admin(
    *,
    title: str,
    message: str,
    error_type: str = "error",
    deduplicate_key: str | None = None,
    is_critical: bool = True,
) -> bool:
    """
    Отправить оповещение администратору в Telegram.

    Returns True если сообщение отправлено.
    """
    if not getattr(settings, "TELEGRAM_ALERTS_ENABLED", True):
        logger.debug("Telegram alerts disabled, skip: %s", title[:80])
        return False

    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    chat_id = getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", "") or ""
    if not token or not chat_id:
        logger.warning("Telegram alerts not configured (token or chat_id missing)")
        return False

    ttl = int(getattr(settings, "TELEGRAM_ALERT_DEDUP_TTL", 3600))
    if deduplicate_key and not is_critical:
        cache_key = f"alert_dedup:{deduplicate_key}"
        if cache.get(cache_key):
            logger.debug("Skipping duplicate alert: %s", deduplicate_key)
            return False

    formatted = format_alert_message(title, message, error_type)
    ok, detail = send_admin_alert(formatted)
    if ok:
        if deduplicate_key and not is_critical:
            cache.set(f"alert_dedup:{deduplicate_key}", True, ttl)
        logger.info("Alert sent to admin: %s", title[:120])
        return True

    logger.warning("Failed to send alert (%s): %s", detail, title[:120])
    return False
