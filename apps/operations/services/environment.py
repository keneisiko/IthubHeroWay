"""Проверка окружения для деструктивных операций.

Часть management-команд создаёт фиктивные данные или перезаписывает поля
существующих пользователей. Такие команды не должны запускаться в продакшене
по неосторожности — раньше у них не было никакой защиты.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import CommandError

PRODUCTION_NAMES = {"production", "prod", "prd"}


def is_production() -> bool:
    env = str(getattr(settings, "ENVIRONMENT_NAME", "development")).strip().lower()
    return env in PRODUCTION_NAMES or not settings.DEBUG and env not in {"development", "dev", "test", "local"}


def ensure_not_production(operation: str, *, allow_force: bool = False, force: bool = False) -> None:
    """Прервать выполнение, если окружение похоже на продакшен."""
    if not is_production():
        return
    if allow_force and force:
        return
    hint = " Добавьте --force, если действительно этого хотите." if allow_force else ""
    raise CommandError(
        f"{operation} запрещено в продакшене "
        f"(ENVIRONMENT_NAME={getattr(settings, 'ENVIRONMENT_NAME', '')!r}, DEBUG={settings.DEBUG}).{hint}"
    )
