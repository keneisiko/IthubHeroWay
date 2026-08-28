"""Привязка аккаунта платформы к Telegram.

Активация подтверждается вводом учебной почты и пароля от LXP прямо в чате,
поэтому здесь же живут ограничения на частоту попыток: без них бот —
готовый инструмент для перебора паролей от колледжа.
"""

from __future__ import annotations

import hashlib
import logging

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError

from apps.integrations.models import TelegramAccountLink

logger = logging.getLogger(__name__)

# Окно и лимиты подобраны так, чтобы живой студент, ошибившийся паролем
# пару раз, не упёрся, а перебор стал бессмысленным.
ATTEMPT_WINDOW_SECONDS = 3600
MAX_ATTEMPTS_PER_TELEGRAM_USER = 5
MAX_ATTEMPTS_PER_EMAIL = 5


def _email_key(email: str) -> str:
    digest = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:32]
    return f"tg:activate:email:{digest}"


def _user_key(telegram_user_id: int) -> str:
    return f"tg:activate:tg:{telegram_user_id}"


def _bump(key: str) -> int:
    """Увеличить счётчик попыток, не сбрасывая окно."""
    if cache.add(key, 1, ATTEMPT_WINDOW_SECONDS):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        # Ключ истёк между add и incr — начинаем окно заново.
        cache.set(key, 1, ATTEMPT_WINDOW_SECONDS)
        return 1


def attempts_exceeded(*, telegram_user_id: int, email: str) -> bool:
    """Проверить лимиты до обращения к LXP.

    Считаем в двух измерениях: по Telegram-аккаунту (один человек перебирает
    пароли к разным почтам) и по почте (несколько аккаунтов перебирают пароль
    к одной жертве).
    """
    by_user = _bump(_user_key(telegram_user_id))
    by_email = _bump(_email_key(email)) if email else 0
    if by_user > MAX_ATTEMPTS_PER_TELEGRAM_USER or by_email > MAX_ATTEMPTS_PER_EMAIL:
        logger.warning(
            "Активация Telegram: превышен лимит попыток (tg_user=%s, по пользователю=%s, по почте=%s)",
            telegram_user_id,
            by_user,
            by_email,
        )
        return True
    return False


def reset_attempts(*, telegram_user_id: int, email: str) -> None:
    """Сбросить счётчики после успешной активации."""
    cache.delete(_user_key(telegram_user_id))
    if email:
        cache.delete(_email_key(email))


def activate_telegram_account(
    *,
    email: str,
    telegram_user_id: int,
    telegram_chat_id: int,
    telegram_username: str,
) -> tuple[bool, str]:
    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return False, "Пользователь с такой почтой не найден в платформе."

    # Этот Telegram-аккаунт мог быть привязан к другому студенту: поле уникально,
    # и без явной проверки получили бы IntegrityError вместо понятного ответа.
    conflicting = (
        TelegramAccountLink.objects.filter(telegram_user_id=telegram_user_id)
        .exclude(user=user)
        .first()
    )
    if conflicting:
        logger.warning(
            "Активация Telegram: аккаунт %s уже привязан к пользователю %s",
            telegram_user_id,
            conflicting.user_id,
        )
        return False, "Этот Telegram-аккаунт уже привязан к другому студенту."

    try:
        TelegramAccountLink.objects.update_or_create(
            user=user,
            defaults={
                "telegram_user_id": telegram_user_id,
                "telegram_chat_id": telegram_chat_id,
                "telegram_username": telegram_username or "",
                "is_active": True,
            },
        )
    except IntegrityError:
        return False, "Не удалось привязать аккаунт: конфликт Telegram-идентификаторов."

    # Привязка Telegram — единственный момент, когда студент подтвердил, что
    # аккаунт его. До этого импортированная из LXP карточка неактивна и войти
    # по ней нельзя (см. import_lxp_students).
    activation_fields: list[str] = []
    if not user.is_active:
        user.is_active = True
        activation_fields.append("is_active")
    if user.status == "imported_lxp":
        user.status = "activated_telegram"
        activation_fields.append("status")
    if activation_fields:
        user.save(update_fields=activation_fields)

    reset_attempts(telegram_user_id=telegram_user_id, email=email)
    return True, f"Аккаунт активирован для {user.username}."
