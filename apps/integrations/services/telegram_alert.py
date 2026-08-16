"""Централизованные Telegram-оповещения об ошибках с дедупликацией."""

from __future__ import annotations

import logging
import re

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.integrations.services.telegram_notify import send_admin_alert

logger = logging.getLogger(__name__)

# Последний рубеж: даже если секрет просочился в текст исключения, в чат он
# не уйдёт. Основная защита — не класть тела ответов в сообщения об ошибках.
_SECRET_PATTERNS = (
    # JWT
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+"),
    # "accessToken": "...", token=..., password: '...'
    re.compile(
        r"(?i)\b(access_?token|refresh_?token|token|password|passwd|secret|api_?key|authorization|cookie|sessionid)"
        r"(\"?\s*[:=]\s*\"?)([^\s\"',;}]{4,})"
    ),
)


def mask_secrets(text: str) -> str:
    """Заменить в тексте всё, что похоже на токен, пароль или ключ."""
    if not text:
        return text
    masked = _SECRET_PATTERNS[0].sub("<токен скрыт>", text)
    masked = _SECRET_PATTERNS[1].sub(lambda m: f"{m.group(1)}{m.group(2)}<скрыто>", masked)
    return masked

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
    body = mask_secrets((message or "").strip())
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

    # Дедупликация нужна и критичным алертам, просто с более коротким окном.
    # Раньше она к ним не применялась вовсе, а Celery шлёт все падения задач
    # как критичные: одна регулярно падающая задача превращала чат в поток
    # одинаковых сообщений, где терялось всё остальное.
    ttl = int(getattr(settings, "TELEGRAM_ALERT_DEDUP_TTL", 3600))
    if is_critical:
        ttl = int(getattr(settings, "TELEGRAM_CRITICAL_DEDUP_TTL", max(300, ttl // 6)))

    cache_key = f"alert_dedup:{deduplicate_key}" if deduplicate_key else None
    if cache_key and cache.get(cache_key):
        logger.debug("Skipping duplicate alert: %s", deduplicate_key)
        return False

    formatted = format_alert_message(title, message, error_type)
    ok, detail = send_admin_alert(formatted)
    if ok:
        if cache_key:
            cache.set(cache_key, True, ttl)
        logger.info("Alert sent to admin: %s", title[:120])
        return True

    logger.warning("Failed to send alert (%s): %s", detail, title[:120])
    return False
