"""Единая точка начисления рейтинга и монет по Положению.

Все разделы Положения начисляют одинаково: рейтинг и монеты одним основанием,
с указанием периода и того, кто подтвердил. Поэтому начисление одно на всех,
а разделы отличаются только тарифом и ключом идемпотентности.

Чем это отличается от `rewards.apply_rating_delta_with_cap`:

* монеты начисляются вместе с рейтингом, а не отдельным вызовом;
* дневной предел монет не применяется — его в Положении нет, а ставки
  разделов 4-7 (до 100 монет за проект) он бы срезал;
* правило анти-накрутки по незакрытым КТ не применяется: Положение не знает
  такого ограничения, а рейтинг по нему не имеет потолка (п. 1.3).

Дневной предел и анти-накрутка остаются у квестов и нашивок — они Положением
не регулируются.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.accounts.models import User
from apps.operations.services.cache import invalidate_rating_views
from apps.progress.models import RatingChangeSource, RatingLog
from apps.progress.services.polozhenie_period import quantize_money

logger = logging.getLogger(__name__)

# п. 2.4: рейтинг не может быть ниже нуля. Верхней границы нет (п. 1.3).
RATING_FLOOR = Decimal("0")


@dataclass(frozen=True)
class LedgerResult:
    applied: bool
    rating_delta: Decimal
    coins_delta: Decimal
    reason: str = ""

    @property
    def skipped_duplicate(self) -> bool:
        return not self.applied


def already_applied(user_id: int, source_id: str) -> bool:
    return RatingLog.objects.filter(user_id=user_id, source_id=source_id).exists()


@transaction.atomic
def grant(
    user: User,
    *,
    rating: Decimal | int | float = 0,
    coins: Decimal | int | float = 0,
    source: str,
    source_id: str,
    reason: str,
    period: str = "",
    confirmed_by: User | None = None,
) -> LedgerResult:
    """Начислить (или списать) по Положению ровно один раз на `source_id`.

    Повторный вызов с тем же `source_id` ничего не делает: п. 2.4 запрещает
    оплачивать один расчётный период дважды, а ответственный может нажать
    кнопку подтверждения второй раз.
    """
    rating_delta = quantize_money(rating)
    coins_delta = quantize_money(coins)

    if rating_delta == 0 and coins_delta == 0:
        return LedgerResult(False, Decimal("0"), Decimal("0"), "nothing_to_grant")

    # Блокируем студента, а не только проверяем журнал: две задачи, стартовавшие
    # одновременно, иначе обе увидят «не начислено» и начислят дважды.
    locked = User.objects.select_for_update().get(pk=user.pk)

    if already_applied(locked.pk, source_id):
        return LedgerResult(False, Decimal("0"), Decimal("0"), "already_applied")

    before = Decimal(str(locked.rating_current))
    after = before + rating_delta
    if after < RATING_FLOOR:
        # п. 2.4: рейтинг не может быть ниже нуля. Списание срезается, а не
        # уводит студента в минус, и в журнал попадает фактическая величина.
        after = RATING_FLOOR
    applied_rating = quantize_money(after - before)

    coins_after = Decimal(str(locked.coins_balance)) + coins_delta
    if coins_after < 0:
        coins_after = Decimal("0")
    applied_coins = quantize_money(coins_after - Decimal(str(locked.coins_balance)))

    locked.rating_current = after
    locked.coins_balance = coins_after
    locked.save(update_fields=["rating_current", "coins_balance"])

    RatingLog.objects.create(
        user=locked,
        value_before=before,
        value_after=after,
        delta=applied_rating,
        coins_delta=applied_coins,
        source=source,
        source_id=source_id,
        reason=reason[:255],
        period_key=period,
        confirmed_by=confirmed_by,
    )
    invalidate_rating_views(locked.username)

    # Объект, переданный вызывающим кодом, должен увидеть новое состояние:
    # иначе цикл по студентам продолжит считать по устаревшему балансу.
    user.rating_current = after
    user.coins_balance = coins_after

    logger.info(
        "polozhenie_grant user=%s source=%s id=%s rating=%s coins=%s",
        locked.pk,
        source,
        source_id,
        applied_rating,
        applied_coins,
    )
    return LedgerResult(True, applied_rating, applied_coins, reason)


def correct(
    user: User,
    *,
    rating: Decimal | int | float = 0,
    coins: Decimal | int | float = 0,
    source_id: str,
    reason: str,
    confirmed_by: User | None = None,
) -> LedgerResult:
    """Исправление ошибочного начисления (п. 9.4, 10.3).

    Отдельная запись с основанием, а не правка старой: Положение требует,
    чтобы исправление было видно в истории и не выглядело как повторное
    начисление за тот же период. Исправление может затрагивать и монеты —
    в отличие от штрафа, который монет не касается.
    """
    return grant(
        user,
        rating=rating,
        coins=coins,
        source=RatingChangeSource.CORRECTION,
        source_id=source_id,
        reason=reason,
        confirmed_by=confirmed_by,
    )
