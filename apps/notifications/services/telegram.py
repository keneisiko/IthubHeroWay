"""Отправка сообщений студенту в Telegram.

`telegram_notify.send_admin_alert` умеет писать только в админский чат —
это канал для ошибок. Студенту писать было нечем, поэтому половина механик
оставалась невидимой: вызвали на дуэль, отклонили подтверждение, начислили
респект — человек узнавал об этом, только если сам заходил и замечал.

Адрес берётся из привязки Telegram: она же служит подтверждением аккаунта,
так что у всех, кто вообще может войти на платформу, чат известен.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings

from apps.integrations.models import TelegramAccountLink

logger = logging.getLogger(__name__)

TELEGRAM_TIMEOUT = 8


def notifications_enabled() -> bool:
    if not getattr(settings, "TELEGRAM_NOTIFICATIONS_ENABLED", True):
        return False
    return bool(getattr(settings, "TELEGRAM_BOT_TOKEN", ""))


def chat_id_for(user) -> int | None:
    link = TelegramAccountLink.objects.filter(user=user, is_active=True).only("telegram_chat_id").first()
    return link.telegram_chat_id if link else None


def send_message(chat_id: int, text: str) -> tuple[bool, str]:
    """Отправить сообщение в конкретный чат.

    Ошибки не поднимаются наружу: уведомление — побочный эффект действия,
    и падение Telegram не должно валить запрос, который его породил.
    """
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    if not token:
        return False, "skipped:no_token"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True},
            timeout=TELEGRAM_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("Уведомление не отправлено (chat=%s): %s", chat_id, exc)
        return False, f"request_error:{exc}"

    if response.status_code != 200:
        logger.warning(
            "Уведомление отклонено Telegram (chat=%s, http=%s): %s",
            chat_id,
            response.status_code,
            response.text[:300],
        )
        return False, f"http_{response.status_code}"
    return True, "ok"


def notify_user(user, text: str) -> bool:
    """Написать студенту. Возвращает, ушло ли сообщение."""
    if not notifications_enabled():
        return False
    chat_id = chat_id_for(user)
    if not chat_id:
        # Аккаунт без привязки — не ошибка: студент мог не активироваться.
        return False
    ok, _ = send_message(chat_id, text)
    return ok


def notify_users(users, text: str) -> int:
    return sum(1 for user in users if notify_user(user, text))
