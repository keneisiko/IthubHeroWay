"""Единственная точка чтения настроек платформы.

Раньше каждое место читало своё число напрямую из `settings`, и у каждого
был свой запасной вариант — причём разный: дневной предел монет в настройках
10, а в запасном значении 20; ставка дуэли 3 против 5. Пока настройка на
месте, расхождение не видно, но это мина. Теперь значения по умолчанию
живут в одном словаре, а читается всё через `platform_setting()`.

Значения кешируются: настройки читаются на каждом начислении, а меняются
раз в несколько недель. Сохранение в админке сбрасывает кеш сразу.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError

logger = logging.getLogger(__name__)

CACHE_KEY = "platform_settings:v1"
CACHE_TTL_SECONDS = 300


def default_values() -> dict[str, Any]:
    """Заводские значения — те, что действовали до появления экрана настроек.

    Читаются из прежних мест (`RATING_LIMITS`, `polozhenie.py`, `.env.prod`),
    поэтому миграция заводит строку с текущими боевыми значениями, а не с
    выдуманными, и поведение до первой правки не меняется.
    """
    limits = getattr(settings, "RATING_LIMITS", {})
    return {
        "max_daily_coins": int(limits.get("MAX_DAILY_COINS", 10)),
        "max_daily_self_reports": int(limits.get("MAX_DAILY_SELF_REPORTS", 3)),
        "squad_weekly_bonus_percent": int(limits.get("SQUAD_WEEKLY_BONUS_PERCENT", 80)),
        "squad_weekly_bonus_coins": int(limits.get("SQUAD_WEEKLY_BONUS_COINS", 3)),
        "respect_weekly_limit": int(limits.get("RESPECT_WEEKLY_LIMIT", 1)),
        "duel_bet": int(limits.get("DUEL_BET", 3)),
        "duel_duration_days": int(limits.get("DUEL_DURATION_DAYS", 7)),
        "duel_invite_ttl_days": int(limits.get("DUEL_INVITE_TTL_DAYS", 3)),
        "duel_max_rating_diff": int(limits.get("DUEL_MAX_RATING_DIFF", 150)),
        "hik_late_grace_minutes": int(getattr(settings, "HIK_LATE_GRACE_MINUTES", 10)),
        "ct_scope": str(getattr(settings, "POLOZHENIE_CT_SCOPE", "deferred")),
        "ct_min_actual": int(getattr(settings, "POLOZHENIE_CT_MIN_ACTUAL", 3)),
        "require_telegram_link_for_scoring": bool(
            getattr(settings, "REQUIRE_TELEGRAM_LINK_FOR_SCORING", False)
        ),
    }


def _load() -> dict[str, Any]:
    from apps.operations.models import PlatformSettings

    values = default_values()
    try:
        row = PlatformSettings.objects.filter(pk=PlatformSettings.SINGLETON_PK).values().first()
    except DatabaseError:
        # Таблицы ещё нет (до миграции) или база недоступна: работаем на
        # заводских значениях, а не падаем — начисление важнее экрана.
        logger.warning("Настройки платформы недоступны, используются заводские значения")
        return values
    if row:
        values.update({key: row[key] for key in values if key in row})
    return values


def platform_settings() -> dict[str, Any]:
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached
    values = _load()
    cache.set(CACHE_KEY, values, CACHE_TTL_SECONDS)
    return values


def platform_setting(name: str) -> Any:
    values = platform_settings()
    if name not in values:
        # Опечатка в имени должна падать громко, а не возвращать None,
        # который где-нибудь превратится в ноль монет.
        raise KeyError(f"Неизвестная настройка платформы: {name}")
    return values[name]


def invalidate() -> None:
    cache.delete(CACHE_KEY)


# Настройки, из которых берутся заводские значения. Если тест подменяет одну
# из них через override_settings, строка в базе должна это отразить.
SOURCE_SETTINGS = frozenset(
    {
        "RATING_LIMITS",
        "HIK_LATE_GRACE_MINUTES",
        "POLOZHENIE_CT_SCOPE",
        "POLOZHENIE_CT_MIN_ACTUAL",
        "REQUIRE_TELEGRAM_LINK_FOR_SCORING",
    }
)


def sync_with_overridden_settings(*, setting: str, **kwargs) -> None:
    """Приёмник сигнала `setting_changed` — его шлёт только override_settings.

    Без него десятки тестов, подменяющих RATING_LIMITS и соседей, продолжали
    бы проходить, проверяя при этом значения из базы, а не те, что записаны
    в самом тесте. Тест, который молча проверяет не то, хуже упавшего.
    """
    if setting not in SOURCE_SETTINGS:
        return
    from apps.operations.models import PlatformSettings

    try:
        PlatformSettings.objects.update_or_create(
            pk=PlatformSettings.SINGLETON_PK, defaults=default_values()
        )
    except DatabaseError:
        # Подмена до создания тестовой базы (на уровне класса): строки ещё
        # нет, и её заведёт миграция уже с подменёнными значениями.
        pass
    invalidate()
