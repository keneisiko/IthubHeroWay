from apps.accounts.models import User
from django.core.cache import cache
from apps.quests.models import UserQuestProgress

from .models import Badge, UserBadge


def _condition_matches(user: User, badge: Badge) -> bool:
    """
    Minimal rule engine for MVP.
    Supported condition:
      {"completed_quests_at_least": <int>}
    """
    condition = badge.condition or {}
    completed_quests_at_least = condition.get("completed_quests_at_least")
    if completed_quests_at_least is not None:
        completed_count = UserQuestProgress.objects.filter(user=user, is_completed=True).count()
        return completed_count >= int(completed_quests_at_least)
    return False


def award_badges_for_user(user: User) -> list[UserBadge]:
    awarded: list[UserBadge] = []
    for badge in Badge.objects.filter(is_active=True):
        if not _condition_matches(user, badge):
            continue
        user_badge, created = UserBadge.objects.get_or_create(
            user=user,
            badge=badge,
            defaults={"source": "rule_engine"},
        )
        if created:
            if badge.reward_coins:
                user.coins_balance += badge.reward_coins
                user.save(update_fields=["coins_balance"])
            cache.delete_pattern(f"profile:{user.username}*")
            cache.delete_pattern("leaderboard:*")
            awarded.append(user_badge)
    return awarded

