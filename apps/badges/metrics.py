"""Метрики, по которым выдаются нашивки.

Движок выдачи понимал одно условие — число выполненных квестов. Поэтому
каталог состоял из трёх нашивок, которые по сути одна метрика с разными
порогами: студент получал все три за первую неделю и дальше не получал
ничего. Данные для остальных давно лежат в базе — серии, контрольные точки,
рейтинг, покупки, респекты, дуэли, опоры, — им не хватало только способа
попасть в условие.

Теперь условие нашивки — это имя метрики и порог:

    {"rating_at_least": 400}
    {"late_streak_at_least": 10}
    {"telegram_linked": true}

Добавить нашивку стало правкой каталога, а не кодом. Добавить **метрику** —
одна функция здесь.

Считаются только те метрики, которые упомянуты в активных нашивках: иначе
каждый еженедельный прогон делал бы десяток запросов на студента ради
условий, которых в каталоге нет.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from django.db.models import Max, Sum

from apps.accounts.models import User

# Условие, означающее «выдаёт человек»: автопроверке тут делать нечего.
MANUAL_CONDITION_KEY = "manual"


def _completed_quests(user: User) -> int:
    from apps.quests.models import UserQuestProgress

    return UserQuestProgress.objects.filter(user=user, is_completed=True).count()


def _completed_weekly_quests(user: User) -> int:
    from apps.quests.models import QuestType, UserQuestProgress

    return UserQuestProgress.objects.filter(
        user=user, is_completed=True, quest__quest_type=QuestType.WEEKLY
    ).count()


def _rating(user: User) -> Decimal:
    return Decimal(str(user.rating_current))


def _late_streak(user: User) -> int:
    strike = getattr(user, "strike", None)
    return int(strike.late_strike) if strike else 0


def _attendance_streak(user: User) -> int:
    strike = getattr(user, "strike", None)
    return int(strike.attendance_strike) if strike else 0


def _ct_closed(user: User) -> int:
    """Сколько контрольных точек студент закрыл с подключения платформы.

    Темы, зафиксированные первым снимком, не считаются: они закрыты до
    того, как платформа начала смотреть.
    """
    from apps.progress.models import LXPTopicState

    state = LXPTopicState.objects.filter(user=user).first()
    if state is None or not isinstance(state.topics, dict):
        return 0
    from datetime import date

    from apps.operations.services.platform_settings import accruals_start_date

    started_on = accruals_start_date()
    count = 0
    for entry in state.topics.values():
        if not isinstance(entry, dict) or not entry.get("closed") or entry.get("baseline"):
            continue
        if started_on is not None:
            # Тема, закрытая до запуска начислений, не считается.
            try:
                if date.fromisoformat(str(entry.get("since"))) < started_on:
                    continue
            except (TypeError, ValueError):
                continue
        count += 1
    return count


def _respects_given(user: User) -> int:
    from apps.social.models import Respect

    return Respect.objects.filter(from_user=user).count()


def _respects_received(user: User) -> int:
    from apps.social.models import Respect

    return Respect.objects.filter(to_user=user).count()


def _duels_won(user: User) -> int:
    from apps.social.models import Duel

    return Duel.objects.filter(winner=user).count()


def _purchases(user: User) -> int:
    from apps.shop.models import Purchase

    return Purchase.objects.filter(user=user).count()


def _coins_spent(user: User) -> Decimal:
    from apps.shop.models import Purchase

    total = Purchase.objects.filter(user=user).aggregate(total=Sum("coins_spent"))["total"]
    return Decimal(str(total or 0))


def _max_pillar(user: User) -> Decimal:
    """Самая развитая опора студента по шкале 0–20."""
    from apps.operations.services.platform_settings import accruals_start_date
    from apps.progress.models import Characteristic

    rows = Characteristic.objects.filter(user=user)
    started_on = accruals_start_date()
    if started_on is not None:
        # Характеристика пересчитывается раз в неделю и хранит накопленное
        # значение: посчитанное до запуска начислений в зачёт не идёт.
        rows = rows.filter(last_updated__date__gte=started_on)
    top = rows.aggregate(top=Max("current"))["top"]
    return Decimal(str(top or 0))


def _badges_owned(user: User) -> int:
    from apps.badges.models import UserBadge

    return UserBadge.objects.filter(user=user).count()


def _telegram_linked(user: User) -> bool:
    link = getattr(user, "telegram_link", None)
    return bool(link and link.is_active)


# Условие → как посчитать метрику. Имя ключа заканчивается на `_at_least`
# у порогов и читается как флаг у остальных.
THRESHOLD_METRICS: dict[str, Callable[[User], Decimal | int]] = {
    "completed_quests_at_least": _completed_quests,
    "completed_weekly_quests_at_least": _completed_weekly_quests,
    "rating_at_least": _rating,
    "late_streak_at_least": _late_streak,
    "attendance_streak_at_least": _attendance_streak,
    "ct_closed_at_least": _ct_closed,
    "respects_given_at_least": _respects_given,
    "respects_received_at_least": _respects_received,
    "duels_won_at_least": _duels_won,
    "purchases_at_least": _purchases,
    "coins_spent_at_least": _coins_spent,
    "max_pillar_at_least": _max_pillar,
    "badges_at_least": _badges_owned,
}

FLAG_METRICS: dict[str, Callable[[User], bool]] = {
    "telegram_linked": _telegram_linked,
}

SUPPORTED_CONDITION_KEYS = set(THRESHOLD_METRICS) | set(FLAG_METRICS) | {MANUAL_CONDITION_KEY}

# Как метрики называются для людей — в форме нашивки в админке. Без этого
# сотрудник должен был сам писать JSON вида {"rating_at_least": 250}.
METRIC_LABELS: dict[str, str] = {
    "completed_quests_at_least": "Выполнено квестов, не меньше",
    "completed_weekly_quests_at_least": "Выполнено недельных квестов, не меньше",
    "rating_at_least": "Рейтинг, не меньше",
    "late_streak_at_least": "Дней подряд без опозданий, не меньше",
    "attendance_streak_at_least": "Дней подряд без пропусков, не меньше",
    "ct_closed_at_least": "Закрыто контрольных точек, не меньше",
    "respects_given_at_least": "Отправлено респектов, не меньше",
    "respects_received_at_least": "Получено респектов, не меньше",
    "duels_won_at_least": "Выиграно дуэлей, не меньше",
    "purchases_at_least": "Покупок в магазине, не меньше",
    "coins_spent_at_least": "Потрачено монет, не меньше",
    "max_pillar_at_least": "Лучшая характеристика, не меньше",
    "badges_at_least": "Собрано нашивок, не меньше",
    "telegram_linked": "Привязал Telegram (число не нужно)",
}


def required_metrics(conditions) -> set[str]:
    """Какие метрики нужны этому набору условий.

    Нужен, чтобы не считать то, чего нет в каталоге: без этого каждый
    прогон делал бы десяток запросов на студента ради неиспользуемых
    условий.
    """
    needed: set[str] = set()
    for condition in conditions:
        if not isinstance(condition, dict):
            continue
        for key in condition:
            if key in THRESHOLD_METRICS or key in FLAG_METRICS:
                needed.add(key)
    return needed


def compute(user: User, names: set[str]) -> dict[str, Decimal | int | bool]:
    """Посчитать названные метрики одного студента."""
    values: dict[str, Decimal | int | bool] = {}
    for name in names:
        if name in THRESHOLD_METRICS:
            values[name] = THRESHOLD_METRICS[name](user)
        elif name in FLAG_METRICS:
            values[name] = FLAG_METRICS[name](user)
    return values
