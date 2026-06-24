from __future__ import annotations

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.progress.models import RatingChangeSource, RatingLog
from apps.quests.models import QuestRewardTransaction


def get_rating_limits() -> dict:
    return getattr(settings, "RATING_LIMITS", {})


def max_daily_coins() -> int:
    return int(get_rating_limits().get("MAX_DAILY_COINS", 20))


def apply_rating_delta_with_cap(user: User, delta: int, source: str, reason: str = "", source_id: str = "") -> int:
    before = user.rating_current
    after = before + delta
    # 2+ unclosed CT blocks growth above 399 for non-manual/system updates.
    if user.unclosed_ct_count >= 2 and delta > 0 and source in {
        RatingChangeSource.QUEST,
        RatingChangeSource.BADGE,
        RatingChangeSource.SOCIAL,
    }:
        after = min(after, 399)
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
    return applied_delta


def remaining_daily_coin_budget(user: User, day_limit: int | None = None) -> int:
    if day_limit is None:
        day_limit = max_daily_coins()
    day_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
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

