import logging
from decimal import Decimal

from django.db import transaction

from apps.accounts.models import User
from apps.badges.metrics import (
    MANUAL_CONDITION_KEY,
    SUPPORTED_CONDITION_KEYS,
    compute,
    required_metrics,
)
from apps.operations.services.cache import invalidate_rating_views
from apps.operations.services.platform_settings import accruals_enabled, require_accruals
from apps.progress.services.rewards import grant_coins_with_daily_cap

from .models import Badge, UserBadge

logger = logging.getLogger(__name__)


def _condition_matches(badge: Badge, metrics: dict) -> bool:
    """Проверить условие нашивки по уже посчитанным метрикам.

    Метрики передаются снаружи: считать их внутри цикла значило бы запрос
    на каждую нашивку каждому студенту.

    Все условия нашивки должны выполняться одновременно. Это позволяет
    описывать «рейтинг выше 400 и серия не меньше десяти дней» одной
    записью каталога.
    """
    condition = badge.condition or {}
    if not isinstance(condition, dict) or not condition:
        return False

    if condition.get(MANUAL_CONDITION_KEY):
        # Нашивку выдаёт куратор. Без этого ключа такие нашивки попадали
        # в «неизвестное условие» и на каждом прогоне сыпали в журнал
        # предупреждения.
        return False

    unknown = set(condition) - SUPPORTED_CONDITION_KEYS
    if unknown:
        # Неизвестное условие раньше молча означало «не выдавать», и
        # опечатка в правиле выглядела как исправно работающая нашивка.
        logger.warning(
            "Значок %s: неизвестные ключи условия %s — значок не будет выдан",
            badge.code,
            sorted(unknown),
        )
        return False

    for key, expected in condition.items():
        value = metrics.get(key)
        if value is None:
            return False
        if isinstance(expected, bool):
            if bool(value) is not expected:
                return False
            continue
        try:
            threshold = Decimal(str(expected))
        except (TypeError, ValueError):
            logger.warning("Значок %s: порог %r не число", badge.code, expected)
            return False
        if Decimal(str(value)) < threshold:
            return False
    return True


def award_badges_for_user(user: User, badges: list[Badge] | None = None) -> list[UserBadge]:
    # Нашивки до запуска не выдаются: у всех должно быть пусто, а выданная
    # сейчас нашивка с наградой стала бы «разовой» и пропала из будущих выдач.
    if not accruals_enabled():
        return []
    if badges is None:
        badges = list(Badge.objects.filter(is_active=True))
    if not badges:
        return []

    already_have = set(
        UserBadge.objects.filter(user=user, badge__in=badges).values_list("badge_id", flat=True)
    )
    pending = [badge for badge in badges if badge.pk not in already_have]
    if not pending:
        return []

    # Считаем только те метрики, которые упомянуты в оставшихся нашивках.
    metrics = compute(user, required_metrics(badge.condition for badge in pending))

    awarded: list[UserBadge] = []
    for badge in pending:
        if not _condition_matches(badge, metrics):
            continue

        # Нашивка и начисление монет — одна операция: без транзакции падение
        # между ними оставляло нашивку без награды, а повторный прогон монеты
        # уже не выдавал, потому что нашивка на месте.
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

        # Нашивка могла сама стать условием другой («собрал десять нашивок»),
        # поэтому зависящие от этого метрики пересчитываем.
        if "badges_at_least" in metrics:
            metrics["badges_at_least"] = int(metrics["badges_at_least"]) + 1

    return awarded


def award_badge_manually(user: User, badge: Badge, *, by: str) -> tuple[bool, int]:
    """Выдать нашивку руками — так же, как автомат: с монетами нашивки.

    Возвращает (выдана ли сейчас, сколько монет начислено). Повторная выдача
    ничего не меняет. Монеты идут через общий дневной предел — как и у
    автоматической выдачи, — поэтому их может прийти меньше награды.
    """
    require_accruals()
    with transaction.atomic():
        user_badge, created = UserBadge.objects.get_or_create(
            user=user, badge=badge, defaults={"source": f"manual:{by}"}
        )
        granted = grant_coins_with_daily_cap(user, badge.reward_coins) if created and badge.reward_coins else 0
    if created:
        invalidate_rating_views(user.username)
    return created, granted
