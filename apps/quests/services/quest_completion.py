"""Idempotent quest completion and reward grant."""

from __future__ import annotations

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.progress.models import RatingChangeSource
from apps.progress.services.rewards import apply_rating_delta_with_cap, remaining_daily_coin_budget
from apps.quests.models import Quest, QuestRewardTransaction, UserQuestProgress


@transaction.atomic
def complete_quest_idempotent(
    user,
    quest: Quest,
    *,
    reason: str,
    evidence: dict | None = None,
    progress_value: float = 1.0,
) -> tuple[UserQuestProgress, bool]:
    """
    Mark quest completed and grant reward once per (user, quest).
    Returns (progress, reward_created).
    """
    progress, _ = UserQuestProgress.objects.select_for_update().get_or_create(user=user, quest=quest)
    if not progress.is_completed:
        progress.is_completed = True
        progress.progress_value = max(progress.progress_value, progress_value)
        progress.completed_at = timezone.now()
        if evidence is not None:
            progress.proof_payload = evidence
        progress.save(
            update_fields=["is_completed", "progress_value", "completed_at", "proof_payload", "updated_at"]
        )

    reward_budget = remaining_daily_coin_budget(user)
    allowed_coins = min(int(quest.reward_coins), reward_budget)
    reward_tx, created = QuestRewardTransaction.objects.get_or_create(
        user=user,
        quest=quest,
        defaults={
            "progress": progress,
            "coins_delta": allowed_coins,
            "rating_delta": quest.reward_rating_delta,
        },
    )
    if created:
        if allowed_coins:
            user.coins_balance += allowed_coins
            user.save(update_fields=["coins_balance"])
        apply_rating_delta_with_cap(
            user=user,
            delta=reward_tx.rating_delta,
            source=RatingChangeSource.QUEST,
            reason=reason[:250],
            source_id=str(quest.id),
        )
        cache.delete(f"profile:{user.username}")
        cache.delete_pattern("leaderboard:*")
        cache.delete_pattern(f"profile:{user.username}*")
    return progress, created


def update_quest_progress(
    user,
    quest: Quest,
    *,
    progress_value: float,
    evidence: dict | None = None,
) -> UserQuestProgress:
    progress, _ = UserQuestProgress.objects.get_or_create(user=user, quest=quest)
    if progress.is_completed:
        return progress
    progress.progress_value = max(0.0, min(1.0, float(progress_value)))
    if evidence is not None:
        progress.proof_payload = evidence
    progress.save(update_fields=["progress_value", "proof_payload", "updated_at"])
    return progress
