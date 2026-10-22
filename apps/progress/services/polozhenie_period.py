"""Расчётный период Положения: неделя и сезон.

Положение считает неделями (п. 2.4) и запрещает оплачивать один и тот же
период дважды. Отсюда ключ периода вида `2026-W43`: он попадает в журнал
начислений и служит защитой от повторной оплаты.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings


def quantize_money(value) -> Decimal:
    """Округление до двух знаков (п. 2.4)."""
    places = int(getattr(settings, "POLOZHENIE_PERIOD", {}).get("DECIMAL_PLACES", 2))
    exp = Decimal(1).scaleb(-places)
    return Decimal(str(value)).quantize(exp, rounding=ROUND_HALF_UP)


def week_start(day: date) -> date:
    """Понедельник недели, в которую попадает день."""
    return day - timedelta(days=day.weekday())


def week_end(day: date) -> date:
    return week_start(day) + timedelta(days=6)


def period_key(day: date) -> str:
    """Ключ расчётной недели по ISO: год и номер недели."""
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def season_start_date() -> date:
    """Первая дата, с которой вообще производятся начисления (п. 2.2).

    День, когда администратор включил начисления, главнее даты из настроек:
    сезон стартует с него, а не с запланированной заранее даты. Данные за дни
    до включения (Hik, LXP) ничего не дают.
    """
    from apps.operations.services.platform_settings import accruals_start_date

    started_on = accruals_start_date()
    if started_on is not None:
        return started_on
    raw = getattr(settings, "POLOZHENIE_PERIOD", {}).get("SEASON_START_DATE", "2026-10-19")
    return date.fromisoformat(str(raw))


def is_payable_week(day: date) -> bool:
    """Оплачивается ли неделя, в которую попадает день.

    Неделя до даты запуска не оплачивается целиком: п. 2.2 говорит «за период
    до запуска начисления не производятся». Неделя, на которую запуск
    приходится, оплачивается — иначе первая неделя сезона пропала бы.
    """
    from apps.operations.services.platform_settings import accruals_enabled

    return accruals_enabled() and week_end(day) >= season_start_date()


def payable_window_start(day: date) -> date:
    """Первый день недели, данные которого оплачиваются.

    В неделе запуска это день включения, а не понедельник: пары, пройденные
    до включения, не засчитываются. Во всех остальных неделях — понедельник.
    """
    return max(week_start(day), season_start_date())
