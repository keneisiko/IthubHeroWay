from __future__ import annotations

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.operations.services.anticheat import apply_unclosed_tests_rule
from apps.operations.services.cache import invalidate_rating_views
from apps.progress.models import RatingChangeSource, RatingLog
from apps.quests.models import QuestRewardTransaction


def get_rating_limits() -> dict:
    return getattr(settings, "RATING_LIMITS", {})


def max_daily_coins() -> int:
    return int(get_rating_limits().get("MAX_DAILY_COINS", 20))


def apply_rating_delta_with_cap(user: User, delta: int, source: str, reason: str = "", source_id: str = "") -> int:
    before = user.rating_current
    after = before + delta

    # Правило анти-накрутки живёт в apps.operations.services.anticheat.
    # Раньше тот модуль не использовался вообще, а пороги (2 незакрытых КТ
    # и потолок 399) были продублированы здесь числами.
    capped_sources = {
        RatingChangeSource.QUEST,
        RatingChangeSource.BADGE,
        RatingChangeSource.SOCIAL,
        # Начисления за «Движ» — тоже награда, а не корректировка: пока висят
        # просроченные КТ, ими нельзя вытянуть рейтинг выше жёлтой зоны.
        RatingChangeSource.DRIVE,
    }
    if delta > 0 and source in capped_sources:
        verdict = apply_unclosed_tests_rule(
            current_rating=before,
            unclosed_tests_count=user.unclosed_ct_count,
        )
        if verdict.hard_cap_rating is not None:
            after = min(after, verdict.hard_cap_rating)
    applied_delta = after - before
    if applied_delta == 0:
        return 0
    user.rating_current = after
    user.save(update_fields=["rating_current"])
    RatingLog.objects.create(
        user=user,
        value_before=before,
        value_after=after,
        delta=applied_delta,
        source=source,
        source_id=source_id,
        reason=reason,
    )
    # Рейтинг изменился — профиль и лидерборды больше не актуальны.
    invalidate_rating_views(user.username)
    return applied_delta


def local_day_start(moment=None):
    """Начало текущих суток в часовом поясе проекта.

    `timezone.now().replace(hour=0, ...)` даёт полночь по UTC, а проект живёт
    в Europe/Moscow: дневные лимиты сбрасывались в 03:00 по местному времени
    и «сутки» захватывали кусок предыдущего дня.
    """
    local = timezone.localtime(moment or timezone.now())
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def remaining_daily_coin_budget(user: User, day_limit: int | None = None) -> int:
    if day_limit is None:
        day_limit = max_daily_coins()
    day_start = local_day_start()
    earned_today = (
        QuestRewardTransaction.objects.filter(user=user, granted_at__gte=day_start).aggregate(total=Sum("coins_delta"))[
            "total"
        ]
        or 0
    )
    return max(0, day_limit - int(earned_today))


def grant_coins_with_daily_cap(user: User, amount: int) -> int:
    """Grant coins respecting MAX_DAILY_COINS (quest ledger only). Returns amount granted."""
    if amount <= 0:
        return 0
    allowed = min(int(amount), remaining_daily_coin_budget(user))
    if allowed:
        user.coins_balance += allowed
        user.save(update_fields=["coins_balance"])
    return allowed

