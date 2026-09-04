import logging

from django.db import transaction

from apps.accounts.models import User
from apps.operations.services.cache import invalidate_rating_views
from apps.progress.services.rewards import grant_coins_with_daily_cap
from apps.quests.models import UserQuestProgress

from .models import Badge, UserBadge

logger = logging.getLogger(__name__)


# `manual` — значок выдаёт человек (куратор), автопроверке тут делать нечего.
# Без этого ключа такие значки попадали в «неизвестное условие» и на каждом
# еженедельном прогоне сыпали предупреждениями в лог.
MANUAL_CONDITION_KEY = "manual"
SUPPORTED_CONDITION_KEYS = {"completed_quests_at_least", MANUAL_CONDITION_KEY}


def _condition_matches(badge: Badge, *, completed_quests: int) -> bool:
    """Проверить условие значка по уже посчитанным метрикам пользователя.

    Метрики передаются снаружи: раньше COUNT по прогрессу квестов выполнялся
    внутри цикла — то есть отдельным запросом на каждый значок.
    """
    condition = badge.condition or {}
    if not isinstance(condition, dict) or not condition:
        return False

    if condition.get(MANUAL_CONDITION_KEY):
        return False

    unknown = set(condition) - SUPPORTED_CONDITION_KEYS
    if unknown:
        # Раньше неизвестное условие молча означало «не выдавать»,
        # и опечатка в правиле выглядела как исправно работающий значок.
        logger.warning(
            "Значок %s: неизвестные ключи условия %s — значок не будет выдан",
            badge.code,
            sorted(unknown),
        )
        return False

    threshold = condition.get("completed_quests_at_least")
    if threshold is None:
        return False
    return completed_quests >= int(threshold)


def award_badges_for_user(user: User) -> list[UserBadge]:
    badges = list(Badge.objects.filter(is_active=True))
    if not badges:
        return []

    # Одна метрика на пользователя вместо запроса на каждый значок.
    completed_quests = UserQuestProgress.objects.filter(user=user, is_completed=True).count()
    already_have = set(
        UserBadge.objects.filter(user=user, badge__in=badges).values_list("badge_id", flat=True)
    )

    awarded: list[UserBadge] = []
    for badge in badges:
        if badge.pk in already_have:
            continue
        if not _condition_matches(badge, completed_quests=completed_quests):
            continue

        # Значок и начисление монет — одна операция: без транзакции падение
        # между ними оставляло значок без награды, а повторный прогон монеты
        # уже не выдавал, потому что значок на месте.
        with transaction.atomic():
            user_badge, created = UserBadge.objects.get_or_create(
                user=user,
                badge=badge,
                defaults={"source": "rule_engine"},
            )
            if not created:
                continue
            if badge.reward_coins:
                grant_coins_with_daily_cap(user, badge.reward_coins)

        invalidate_rating_views(user.username)
        awarded.append(user_badge)

    return awarded

