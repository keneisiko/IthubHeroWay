"""Единая точка инвалидации кеша.

Зачем отдельный модуль:

1. `cache.delete_pattern` есть только у django_redis. На locmem (тесты) это
   AttributeError, поэтому вызовы разбросанные по вьюхам ломали тестовый прогон.
2. Ключи профиля и лидербордов раньше чистились вразнобой: отряды удаляли
   `leaderboard:squads:*`, квесты — `leaderboard:*`, а магазин пытался удалить
   `profile:<username>` — ключ такого вида не создаётся вообще
   (реальный формат — `profile:<username>:viewer:<id>`).

Формат ключей описан здесь же, чтобы не расходился по коду:
- `profile:<username>:viewer:<viewer_id>` — PublicProfileView
- `leaderboard:agents:*`                  — AgentLeaderboardView
- `leaderboard:squads:*`                  — SquadLeaderboardView
"""

from __future__ import annotations

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

PROFILE_KEY_PREFIX = "profile"
LEADERBOARD_KEY_PREFIX = "leaderboard"


def delete_pattern(pattern: str) -> None:
    """Удалить ключи по шаблону.

    На бэкендах без `delete_pattern` (locmem в тестах) деградирует до полной
    очистки кеша: потерять кеш целиком безопаснее, чем отдавать устаревшие
    данные. В проде используется django_redis, где шаблон отрабатывает точечно.
    """
    deleter = getattr(cache, "delete_pattern", None)
    if callable(deleter):
        try:
            deleter(pattern)
            return
        except Exception:  # соединение с Redis не должно ронять запрос
            logger.warning("cache.delete_pattern(%s) failed", pattern, exc_info=True)
            return
    try:
        cache.clear()
    except Exception:
        logger.warning("cache.clear() failed", exc_info=True)


def invalidate_profile(username: str) -> None:
    """Сбросить кеш профиля пользователя для всех, кто его смотрел."""
    if not username:
        return
    delete_pattern(f"{PROFILE_KEY_PREFIX}:{username}:*")


def invalidate_leaderboards() -> None:
    """Сбросить кеш лидербордов агентов и отрядов."""
    delete_pattern(f"{LEADERBOARD_KEY_PREFIX}:*")


def invalidate_squad_leaderboard() -> None:
    """Сбросить только кеш рейтинга отрядов."""
    delete_pattern(f"{LEADERBOARD_KEY_PREFIX}:squads:*")


def invalidate_rating_views(username: str | None = None) -> None:
    """Полный сброс представлений, зависящих от рейтинга.

    Вызывать после любого изменения `User.rating_current`.
    """
    if username:
        invalidate_profile(username)
    invalidate_leaderboards()
