"""Idempotent quest completion and reward grant."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.operations.services.cache import invalidate_rating_views
from apps.operations.services.platform_settings import require_accruals
from apps.progress.models import RatingChangeSource
from apps.progress.services.rewards import apply_rating_delta_with_cap, remaining_daily_coin_budget
from apps.quests.models import Quest, QuestRewardTransaction, UserQuestProgress
from apps.quests.services.weekly_focus import focus_bonus
from apps.shop.models import Purchase
from apps.shop.services import unused_boosts


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

    До запуска платформы выполнение не фиксируется вовсе: ни прогресс, ни
    транзакция награды. Нулевая транзакция заблокировала бы получение
    настоящей награды (она уникальна по паре «студент + квест»).
    """
    require_accruals()
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

    # Надбавка за цель недели: квест, который студент сам выбрал приоритетным.
    bonus_coins, bonus_rating = focus_bonus(user, quest)

    base_coins = int(quest.reward_coins) + bonus_coins
    # Буст берём под блокировкой до расчёта награды: две одновременные
    # завершённые квесты не должны удвоить оба по одному бусту.
    boost = _lock_boost(user) if base_coins > 0 and not _already_rewarded(user, quest) else None
    reward_budget = remaining_daily_coin_budget(user)
    # Дневной предел действует и на удвоенную награду: буст его не обходит.
    allowed_coins = min(base_coins * (2 if boost else 1), reward_budget)
    reward_tx, created = QuestRewardTransaction.objects.get_or_create(
        user=user,
        quest=quest,
        defaults={
            "progress": progress,
            "coins_delta": allowed_coins,
            "rating_delta": quest.reward_rating_delta + bonus_rating,
        },
    )
    if created and (bonus_coins or bonus_rating):
        reason = f"{reason} (цель недели: +{bonus_coins} монет, +{bonus_rating} рейтинга)"
    # Буст тратится, только если он реально что-то дал: если предел дня и так
    # дал бы ту же сумму (остаток лимита меньше базы), он остаётся на следующий квест.
    if created and boost is not None and allowed_coins > min(base_coins, reward_budget):
        boost.consumed_at = timezone.now()
        boost.meta = {
            **(boost.meta or {}),
            "boost": {"quest_id": quest.id, "base_coins": base_coins, "granted_coins": allowed_coins},
        }
        boost.save(update_fields=["consumed_at", "meta"])
        reason = f"{reason} (буст ×2: монеты {base_coins} → {allowed_coins})"
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
        invalidate_rating_views(user.username)
    return progress, created


def _already_rewarded(user, quest: Quest) -> bool:
    return QuestRewardTransaction.objects.filter(user=user, quest=quest).exists()


def _lock_boost(user) -> Purchase | None:
    """Самый ранний неиспользованный буст студента, заблокированный до конца транзакции."""
    return (
        unused_boosts(user)
        .select_for_update()
        .order_by("created_at", "id")
        .first()
    )


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
