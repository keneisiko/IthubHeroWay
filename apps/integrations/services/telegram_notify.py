from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_admin_alert(text: str) -> tuple[bool, str]:
    """
    Отправляет текст администратору в Telegram.
    Возвращает (успех, деталь для логов).
    """
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    chat_id = getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", "") or ""
    if not token or not chat_id:
        detail = "skipped:not_configured(token_or_chat_id_empty)"
        logger.warning("send_admin_alert %s text_prefix=%s", detail, text[:80])
        return False, detail
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
            timeout=8,
        )
        if resp.status_code != 200:
            detail = f"telegram_http_{resp.status_code}:{resp.text[:400]}"
            logger.warning("send_admin_alert failed %s", detail)
            return False, detail
        return True, "ok"
    except requests.Timeout:
        detail = "telegram_timeout"
        logger.warning("send_admin_alert %s", detail)
        return False, detail
    except requests.RequestException as e:
        detail = f"telegram_request_error:{e}"
        logger.warning("send_admin_alert %s", detail)
        return False, detail
