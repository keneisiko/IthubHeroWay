"""Бонусы за серии без опозданий и пропусков."""

from __future__ import annotations

from django.conf import settings

LATE_STREAK_MILESTONES = (21, 14, 7)
ATTENDANCE_STREAK_MILESTONES = (7,)


def late_streak_bonus_for_days(streak_days: int) -> int:
    kp = getattr(settings, "RATING_KP", {})
    if streak_days >= 21:
        return int(kp.get("LATE_STREAK_21D", 15))
    if streak_days >= 14:
        return int(kp.get("LATE_STREAK_14D", 10))
    if streak_days >= 7:
        return int(kp.get("LATE_STREAK_7D", 5))
    return 0


def attendance_streak_bonus_for_days(streak_days: int) -> int:
    kp = getattr(settings, "RATING_KP", {})
    if streak_days >= 7:
        return int(kp.get("ATTENDANCE_STREAK_7D", 5))
    return 0


def late_streak_milestone(streak_days: int) -> int:
    """Достигнутая веха серии без опозданий: 21, 14, 7 или 0.

    Награда назначается за диапазон дней, а не за конкретный день, поэтому
    ключ начисления должен опираться на веху. Иначе на 8-й, 9-й и далее день
    ключ каждый раз новый, а бонус тот же — и он капает ежедневно.
    """
    for milestone in LATE_STREAK_MILESTONES:
        if streak_days >= milestone:
            return milestone
    return 0


def attendance_streak_milestone(streak_days: int) -> int:
    for milestone in ATTENDANCE_STREAK_MILESTONES:
        if streak_days >= milestone:
            return milestone
    return 0
