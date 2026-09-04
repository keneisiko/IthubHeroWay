"""Цель недели: приоритетный квест студента.

Выбор не отключает другие еженедельные квесты — они остаются активными
и вознаграждаются как обычно. Цель недели поднимает квест в списке
и добавляет небольшую надбавку к награде за него.
"""

from __future__ import annotations

from datetime import date

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.quests.models import Quest, QuestType, WeeklyFocus
from apps.quests.services.quest_periods import period_key_for


class FocusNotAllowed(ValueError):
    pass


def current_period_key(day: date | None = None) -> str:
    return period_key_for(QuestType.WEEKLY, day or timezone.localdate())


def get_focus(user, day: date | None = None) -> WeeklyFocus | None:
    return (
        WeeklyFocus.objects.filter(user=user, period_key=current_period_key(day))
        .select_related("quest")
        .first()
    )


@transaction.atomic
def set_focus(user, quest_code: str, day: date | None = None) -> WeeklyFocus:
    """Назначить цель недели. Повторный вызов заменяет прежнюю."""
    period_key = current_period_key(day)
    quest = Quest.objects.filter(code=quest_code, is_active=True).first()
    if not quest:
        raise FocusNotAllowed("Квест не найден.")
    if quest.quest_type != QuestType.WEEKLY:
        raise FocusNotAllowed("Целью недели может быть только еженедельный квест.")
    # Экземпляры квестов живут по периодам: цель прошлой недели на этой
    # неделе бессмысленна, а квест без периода — не еженедельный экземпляр.
    if quest.period_key and quest.period_key != period_key:
        raise FocusNotAllowed("Этот квест относится к другой неделе.")

    focus, _ = WeeklyFocus.objects.update_or_create(
        user=user, period_key=period_key, defaults={"quest": quest}
    )
    return focus


def is_focused(user, quest: Quest) -> bool:
    if quest.quest_type != QuestType.WEEKLY:
        return False
    period_key = quest.period_key or current_period_key()
    return WeeklyFocus.objects.filter(user=user, quest=quest, period_key=period_key).exists()


def focus_bonus(user, quest: Quest) -> tuple[int, int]:
    """Надбавка (монеты, рейтинг) за выполнение квеста, выбранного целью недели."""
    if not is_focused(user, quest):
        return 0, 0
    rewards = getattr(settings, "QUESTS_REWARDS", {})
    return (
        int(rewards.get("WEEKLY_FOCUS_BONUS_COINS", 5)),
        int(rewards.get("WEEKLY_FOCUS_BONUS_RATING", 3)),
    )
