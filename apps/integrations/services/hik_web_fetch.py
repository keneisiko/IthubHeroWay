"""Забор записей прохода из портала: сессия + HTTP-клиент + один ретрай.

Точка входа для Celery-задач и management-команд. Здесь и только здесь
принимается решение о повторном логине: клиент про браузер ничего не знает,
а модуль сессии ничего не знает про API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time

from django.utils import timezone

from apps.integrations.services.hik_session import drop_session, get_session_cookies
from apps.integrations.services.hik_web_client import HikWebAuthError, HikWebClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HikFetchResult:
    start: datetime
    end: datetime
    rows: list[dict]
    relogin_used: bool

    @property
    def count(self) -> int:
        return len(self.rows)


def day_bounds(target: date) -> tuple[datetime, datetime]:
    """Границы суток в местном времени.

    Считать по UTC нельзя: расписание пар и опоздания живут в Europe/Moscow,
    и сдвиг на три часа перекидывает утренние проходы в предыдущий день.
    """
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(target, time.min), tz)
    end = timezone.make_aware(datetime.combine(target, time.max), tz)
    return start, end


def fetch_rows_for_range(start: datetime, end: datetime) -> HikFetchResult:
    """Забрать записи за диапазон, обновив сессию при её протухании."""
    cookies = get_session_cookies()
    try:
        rows = HikWebClient(cookies).fetch_rows(start, end)
        return HikFetchResult(start=start, end=end, rows=rows, relogin_used=False)
    except HikWebAuthError as exc:
        logger.info("hik_web: сессия недействительна (%s), повторный вход", exc)

    # Единственная повторная попытка: если и после свежего логина 401 —
    # это не протухшая сессия, а проблема доступа, и её надо показать.
    drop_session()
    cookies = get_session_cookies(force_refresh=True)
    rows = HikWebClient(cookies).fetch_rows(start, end)
    return HikFetchResult(start=start, end=end, rows=rows, relogin_used=True)


def fetch_rows_for_date(target: date) -> HikFetchResult:
    start, end = day_bounds(target)
    return fetch_rows_for_range(start, end)
