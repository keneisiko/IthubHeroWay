"""Границы учебного года.

Рейтинг копится за год: 1 сентября все стартуют с одинакового значения,
к лету накопленное показывает вклад за год, а не состояние на сегодня.
"""

from __future__ import annotations

from datetime import date

from django.conf import settings


def _cfg() -> dict:
    return getattr(settings, "RATING_YEAR", {})


def academic_year_start(day: date) -> date:
    """Первое сентября того учебного года, в который попадает дата."""
    cfg = _cfg()
    month = int(cfg.get("ACADEMIC_YEAR_START_MONTH", 9))
    day_of_month = int(cfg.get("ACADEMIC_YEAR_START_DAY", 1))
    boundary = date(day.year, month, day_of_month)
    return boundary if day >= boundary else date(day.year - 1, month, day_of_month)


def academic_year_label(day: date) -> str:
    """Метка вида `2026/2027` — используется в ключах начислений."""
    start = academic_year_start(day)
    return f"{start.year}/{start.year + 1}"
