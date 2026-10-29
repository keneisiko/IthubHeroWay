"""«Царь горы»: монеты за удержание топа рейтинга.

Платится только монетами — рейтинг не растёт: иначе лидер получал бы баллы
за то, что он лидер, и отрыв увеличивался бы сам собой. Дневной предел монет
за квесты сюда не относится, это отдельная награда (через ledger Положения).

Ежедневно (23:30):
- общий топ студентов: 1-е место 4 монеты, 2-е — 2, 3-е — 1;
- первое место на каждом курсе (1–4) — 1 монета;
- 7 дней подряд на первом месте — разово 15 монет и нашивка «Царь горы»;
- сместивший вчерашнего первого — 5 монет «Свергнул короля».
Еженедельно (понедельник): студентам отряда-лидера по 5 монет.

Порядок мест — как в рейтинге на сайте: по рейтингу, при равенстве по id.
Студент с нулём баллов наград не получает. Каждое начисление — один раз
на свой ключ, повторный запуск ничего не удваивает.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.utils import timezone

from apps.accounts.models import Role, User
from apps.badges.models import Badge
from apps.badges.services import award_badge_manually
from apps.notifications.services.telegram import notify_user
from apps.operations.services.platform_settings import accruals_enabled
from apps.progress.models import RatingChangeSource, RatingLog
from apps.progress.services.polozhenie_ledger import grant

logger = logging.getLogger(__name__)

TOP_REWARDS = (4, 2, 1)
COURSE_LEADER_REWARD = 1
COURSES = (1, 2, 3, 4)
STREAK_DAYS = 7
STREAK_REWARD = 15
DETHRONE_REWARD = 5
SQUAD_LEADER_REWARD = 5
KING_BADGE_CODE = "king-of-hill"


def _ranked(queryset=None):
    base = queryset if queryset is not None else User.objects.all()
    return base.filter(role=Role.AGENT, is_active=True, rating_current__gt=0).order_by("-rating_current", "id")


def _pay(user: User, coins: int, key: str, reason: str, *, once_per_key: bool = True) -> bool:
    # Место за день — одно на всех: если задачу перезапустят, а порядок за это
    # время сменился, второй студент не получит то же место за тот же день.
    if once_per_key and RatingLog.objects.filter(source_id=key).exists():
        return False
    result = grant(user, coins=coins, source=RatingChangeSource.KING, source_id=key, reason=reason)
    return result.applied


def _first_place_holder(day: date) -> int | None:
    return (
        RatingLog.objects.filter(source_id=f"king:top1:{day.isoformat()}")
        .values_list("user_id", flat=True)
        .first()
    )


def _streak(user_id: int, day: date) -> int:
    """Сколько дней подряд, включая `day`, студент был первым."""
    days = 0
    current = day
    while _first_place_holder(current) == user_id:
        days += 1
        current -= timedelta(days=1)
    return days


def pay_daily_top(day: date | None = None) -> dict:
    day = day or timezone.localdate()
    if not accruals_enabled():
        return {"day": day.isoformat(), "skipped": "accruals_disabled"}
    stamp = day.isoformat()
    paid: list[str] = []

    top = list(_ranked()[: len(TOP_REWARDS)])
    for place, (user, coins) in enumerate(zip(top, TOP_REWARDS, strict=False), start=1):
        if _pay(user, coins, f"king:top{place}:{stamp}", f"Царь горы: {place}-е место в рейтинге за {day:%d.%m}"):
            paid.append(f"top{place}:{user.username}")

    if top:
        king = top[0]
        yesterday_king = _first_place_holder(day - timedelta(days=1))
        if yesterday_king and yesterday_king != king.pk:
            if _pay(king, DETHRONE_REWARD, f"king:dethrone:{stamp}", "Свергнул короля: занял первое место"):
                notify_user(king, f"👑 Вы сместили лидера и заняли первое место! +{DETHRONE_REWARD} монет.")
        streak = _streak(king.pk, day)
        if streak and streak % STREAK_DAYS == 0:
            key = f"king:streak:{king.pk}:{stamp}"
            if _pay(king, STREAK_REWARD, key, f"Царь горы: {streak} дней подряд на первом месте"):
                badge = Badge.objects.filter(code=KING_BADGE_CODE, is_active=True).first()
                if badge:
                    award_badge_manually(king, badge, by="king_of_hill")
                notify_user(
                    king,
                    f"👑 {streak} дней подряд на первом месте — вы Царь горы! +{STREAK_REWARD} монет.",
                )

    for course in COURSES:
        leader = _ranked(User.objects.filter(squad__course=course)).first()
        if leader and _pay(
            leader, COURSE_LEADER_REWARD, f"king:course{course}:{stamp}",
            f"Первое место на {course}-м курсе за {day:%d.%m}",
        ):
            paid.append(f"course{course}:{leader.username}")

    logger.info("king_of_hill_daily %s %s", stamp, paid)
    return {"day": stamp, "paid": paid}


def pay_weekly_squad_leader(now=None) -> dict:
    """Понедельник: каждому активированному студенту отряда-лидера по 5 монет."""
    from apps.accounts.squads_views import _squad_stats_queryset

    now = now or timezone.now()
    if not accruals_enabled():
        return {"skipped": "accruals_disabled"}
    last_week = timezone.localdate(now) - timedelta(days=7)
    iso_year, iso_week, _ = last_week.isocalendar()
    week = f"{iso_year}-W{iso_week:02d}"

    leader = (
        _squad_stats_queryset().filter(avg_rating__gt=0).order_by("-avg_rating", "id").first()
    )
    if leader is None:
        return {"week": week, "squad": None, "paid": 0}
    members = User.objects.filter(squad=leader, role=Role.AGENT, is_active=True)
    paid = 0
    for member in members:
        if _pay(
            member, SQUAD_LEADER_REWARD, f"king:squad:{week}",
            f"Отряд «{leader.name}» — лидер недели {week}",
            once_per_key=False,
        ):
            paid += 1
            notify_user(member, f"🏆 Ваш отряд «{leader.name}» — лидер недели! +{SQUAD_LEADER_REWARD} монет.")
    return {"week": week, "squad": leader.code, "paid": paid}
