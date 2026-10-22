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
from datetime import date
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, transaction

logger = logging.getLogger(__name__)

# v2: в словарь добавились ключи accruals_*; словарь v1 из Redis после деплоя
# их не содержит. Старый ключ сбрасывает миграция 0002.
CACHE_KEY = "platform_settings:v2"
LEGACY_CACHE_KEYS = ("platform_settings:v1",)
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
        # До запуска платформа заморожена. Тестовые настройки включают флаг
        # заранее: сотни тестов проверяют начисления, а не выключатель.
        "accruals_enabled": bool(getattr(settings, "ACCRUALS_ENABLED_BY_DEFAULT", False)),
        "accruals_started_on": None,
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
        # Мёрж с заводскими значениями: словарь из кеша, записанный более
        # старой версией кода, не должен давать KeyError на новых ключах.
        return {**default_values(), **cached}
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
    cache.delete_many(list(LEGACY_CACHE_KEYS))


# --- выключатель начислений ----------------------------------------------------

ACCRUALS_OFF_MESSAGE = "Начисления стартуют с запуска платформы."


class AccrualsDisabled(Exception):
    """Начисления выключены: действие, которое что-то начислило бы, не выполняется."""

    def __init__(self, message: str = ACCRUALS_OFF_MESSAGE):
        super().__init__(message)


def accruals_enabled() -> bool:
    return bool(platform_setting("accruals_enabled"))


def accruals_start_date() -> date | None:
    """День, с которого идёт сезон; `None`, пока начисления ни разу не включали."""
    return platform_setting("accruals_started_on")


def accruals_active_on(day: date) -> bool:
    """Можно ли начислять за данные этого дня.

    Данные до даты запуска не оплачиваются никогда, даже после включения:
    иначе включение задним числом выдало бы всем накопившиеся за простой
    баллы разом, а сезон должен стартовать с нуля.
    """
    if not accruals_enabled():
        return False
    started_on = accruals_start_date()
    return started_on is None or day >= started_on


def require_accruals() -> None:
    if not accruals_enabled():
        raise AccrualsDisabled()


def switch_accruals(enabled: bool):
    """Включить или остановить начисления. Возвращает строку настроек.

    Дата старта ставится только на переходе «выключено → включено»: повторное
    нажатие на уже включённых начислениях не должно сдвигать сезон. При
    остановке дата остаётся — по ней видно, с какого дня шёл последний период.
    После остановки и нового включения сезон стартует заново с этого дня.
    """
    from django.utils import timezone

    from apps.operations.models import PlatformSettings

    # Блокировка строки: два одновременных переключения (двойной клик, два
    # администратора) не должны оба увидеть «было выключено» и поставить дату дважды.
    with transaction.atomic():
        PlatformSettings.objects.get_or_create(
            pk=PlatformSettings.SINGLETON_PK, defaults=default_values()
        )
        row = PlatformSettings.objects.select_for_update().get(pk=PlatformSettings.SINGLETON_PK)
        if enabled and not row.accruals_enabled:
            row.accruals_started_on = timezone.localdate()
        row.accruals_enabled = enabled
        row.save()  # save() сбрасывает кеш: переключение действует сразу
    return row


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
        # Выключатель начислений тест подменяет сам, а не через настройки:
        # сброс на заводское значение стёр бы его посреди теста.
        defaults = {
            key: value
            for key, value in default_values().items()
            if not key.startswith("accruals_")
        }
        PlatformSettings.objects.update_or_create(
            pk=PlatformSettings.SINGLETON_PK, defaults=defaults
        )
    except DatabaseError:
        # Подмена до создания тестовой базы (на уровне класса): строки ещё
        # нет, и её заведёт миграция уже с подменёнными значениями.
        pass
    invalidate()
