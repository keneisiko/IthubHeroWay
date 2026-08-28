"""Orchestration: evaluate auto-verifiable quests and apply progress/completion."""

from __future__ import annotations

import logging
from datetime import date

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import Role
from apps.quests.models import Quest, QuestType, QuestVerifierKind
from apps.quests.services.quest_completion import complete_quest_idempotent, update_quest_progress
from apps.quests.services.quest_conditions import is_auto_verified, resolve_verifier_config
from apps.quests.services.quest_periods import ensure_period_quests, quests_for_date
from apps.quests.services.verifiers import run_verifier

logger = logging.getLogger(__name__)
User = get_user_model()


def _active_quests_queryset(quest_types: list[str] | None = None, target_date: date | None = None):
    """Квесты, действующие на дату проверки.

    Периодические квесты живут экземплярами на день/неделю, поэтому выбирать
    их «по текущему моменту» нельзя: проверка за вчера должна брать вчерашний
    экземпляр, а не сегодняшний.
    """
    return quests_for_date(target_date or timezone.localdate(), quest_types)


def _eligible_users():
    return (
        User.objects.filter(role=Role.AGENT, telegram_link__is_active=True)
        .select_related("telegram_link")
        .order_by("id")
    )


def verify_quest_for_user(
    user,
    quest: Quest,
    target_date: date | None = None,
    *,
    verifier_config: tuple[str | None, dict] | None = None,
) -> dict:
    """Проверить один квест у одного пользователя.

    `verifier_config` позволяет вызывающему коду разрешить конфигурацию один
    раз на квест: она зависит только от квеста, но её вычисление лезет
    в таблицу шаблонов, и в массовом прогоне это давало запрос на каждую пару
    «квест × пользователь».
    """
    target_date = target_date or timezone.localdate()
    if not is_auto_verified(quest):
        return {"skipped": True, "reason": "not_auto"}

    verifier, params = verifier_config if verifier_config is not None else resolve_verifier_config(quest)
    if not verifier or verifier == QuestVerifierKind.MANUAL:
        return {"skipped": True, "reason": "manual_verifier"}

    result = run_verifier(user, verifier, params, target_date)
    evidence = {
        **result.evidence,
        "message": result.message,
        "verified_at": timezone.now().isoformat(),
        "target_date": target_date.isoformat(),
    }

    if result.completed:
        progress, reward_created = complete_quest_idempotent(
            user,
            quest,
            reason=f"Auto-verify {quest.code}: {result.message}",
            evidence=evidence,
            progress_value=1.0,
        )
        return {
            "completed": True,
            "reward_created": reward_created,
            "progress": progress.progress_value,
            "message": result.message,
        }

    update_quest_progress(user, quest, progress_value=result.progress, evidence=evidence)
    return {
        "completed": False,
        "progress": result.progress,
        "message": result.message,
    }


def verify_all_auto_quests(
    target_date: date | None = None,
    quest_types: list[str] | None = None,
) -> dict:
    target_date = target_date or timezone.localdate()
    if quest_types is None:
        quest_types = [QuestType.DAILY, QuestType.WEEKLY]

    # Экземпляры на период создаются здесь же: иначе автопроверка в 06:15
    # работала бы по вчерашним квестам, а сегодняшних ещё не существовало бы.
    ensure_period_quests(target_date)
    quests = [q for q in _active_quests_queryset(quest_types, target_date) if is_auto_verified(q)]
    users = list(_eligible_users())

    stats = {
        "date": target_date.isoformat(),
        "quests": len(quests),
        "users": len(users),
        "completed": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    for quest in quests:
        # Конфигурация верификатора зависит только от квеста — разрешаем её
        # один раз, а не на каждого пользователя.
        config = resolve_verifier_config(quest)
        for user in users:
            try:
                outcome = verify_quest_for_user(user, quest, target_date, verifier_config=config)
                if outcome.get("skipped"):
                    stats["skipped"] += 1
                elif outcome.get("completed"):
                    stats["completed"] += 1
                else:
                    stats["updated"] += 1
            except Exception:
                stats["errors"] += 1
                logger.exception("quest_verify_failed quest=%s user=%s", quest.code, user.pk)

    logger.info("verify_all_auto_quests %s", stats)
    return stats
