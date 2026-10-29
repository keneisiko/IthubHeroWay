"""Награды за социальные механики.

Коэффициенты `RESPECT_REWARD`, `MENTEE_WEEKLY_COINS` и `MENTORING` были
описаны в регламенте и заведены в настройках, но не начислялись нигде:
респект отправлялся «в пустоту», а наставник не получал ничего.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import ROUND_DOWN, Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.notifications.services import events
from apps.operations.services.platform_settings import accruals_enabled
from apps.progress.models import RatingChangeSource, RatingLog
from apps.progress.services.rewards import apply_rating_delta_with_cap, grant_coins_with_daily_cap
from apps.social.models import Mentorship


def _rewards() -> dict:
    return getattr(settings, "QUESTS_REWARDS", {})


def grant_respect_reward(respect) -> int:
    """Монеты получателю респекта. Возвращает начисленное.

    Награду получает тот, кого отметили: респект — это признание чужой
    работы, а не действие отправителя.
    """
    amount = int(_rewards().get("RESPECT_REWARD", 3))
    if amount <= 0:
        return 0
    return grant_coins_with_daily_cap(respect.to_user, amount)


# Награда наставника — за успехи подшефного, а не за сам факт шефства.
# Прежние 15 баллов за взятого подшефного и 2 монеты в неделю за каждого
# платились «просто так»: на запуске их фармили, беря и отпуская подшефных.
MENTOR_SHARE = Decimal("0.10")  # доля от недельного прироста подшефного
MENTOR_CAP_PER_MENTEE = Decimal("5")  # потолок за одного подшефного в неделю
MENTOR_MIN_DAYS = 7  # шефство должно длиться неделю, прежде чем приносить баллы

# Что считается успехом подшефного: учёба, квесты, мероприятия, олимпиады,
# проекты, роли и нашивки. Социальные начисления и ручные правки — нет:
# иначе двое наставников-подшефных разгоняли бы друг друга по кругу.
MERIT_SOURCES = (
    RatingChangeSource.ACADEMIC,
    RatingChangeSource.QUEST,
    RatingChangeSource.EVENT,
    RatingChangeSource.OLYMPIAD,
    RatingChangeSource.PROJECT,
    RatingChangeSource.ROLE,
    RatingChangeSource.BADGE,
    RatingChangeSource.DRIVE,
)


def _previous_week(now) -> tuple[datetime, datetime, str]:
    """Прошлая ISO-неделя: [понедельник 00:00, следующий понедельник 00:00)."""
    today = timezone.localtime(now).date()
    this_monday = today - timedelta(days=today.weekday())
    start_day = this_monday - timedelta(days=7)
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(start_day, time.min), tz)
    end = timezone.make_aware(datetime.combine(this_monday, time.min), tz)
    iso_year, iso_week, _ = start_day.isocalendar()
    return start, end, f"{iso_year}-W{iso_week:02d}"


def mentee_week_gain(mentee_id: int, start, end) -> Decimal:
    """Сколько баллов подшефный заработал сам за неделю."""
    total = RatingLog.objects.filter(
        user_id=mentee_id,
        source__in=MERIT_SOURCES,
        delta__gt=0,
        created_at__gte=start,
        created_at__lt=end,
    ).aggregate(total=Sum("delta"))["total"]
    return Decimal(total or 0)


def mentor_reward_for(gain: Decimal) -> Decimal:
    return min(MENTOR_CAP_PER_MENTEE, (gain * MENTOR_SHARE).quantize(Decimal("0.01"), rounding=ROUND_DOWN))


def pay_mentors_weekly(now=None) -> dict:
    """Наставникам — доля от успехов подшефных за прошлую неделю (понедельник).

    Платится за шефство, которое было принято не меньше чем за неделю до конца
    недели и не закончилось до её начала. Ключ — наставник, подшефный и
    неделя: повторный запуск ничего не удваивает. Подшефный, который ничего
    не заработал, ничего не приносит и наставнику.
    """
    now = now or timezone.now()
    start, end, week_key = _previous_week(now)
    if not accruals_enabled():
        return {"week": week_key, "mentors_paid": 0, "points": 0, "skipped": "accruals_disabled"}

    rows = (
        Mentorship.objects.filter(
            accepted_at__isnull=False,
            accepted_at__lte=end - timedelta(days=MENTOR_MIN_DAYS),
        )
        .filter(Q(ended_at__isnull=True) | Q(ended_at__gte=start))
        .select_related("mentor", "mentee")
        .order_by("mentor_id")
    )
    paid = 0
    points = Decimal(0)
    User = get_user_model()
    for mentorship in rows:
        source_id = f"mentor_merit:{mentorship.mentee_id}:{week_key}"
        if RatingLog.objects.filter(user_id=mentorship.mentor_id, source_id=source_id).exists():
            continue
        reward = mentor_reward_for(mentee_week_gain(mentorship.mentee_id, start, end))
        if reward <= 0:
            continue
        with transaction.atomic():
            mentor = User.objects.select_for_update().get(pk=mentorship.mentor_id)
            applied = apply_rating_delta_with_cap(
                user=mentor,
                delta=reward,
                source=RatingChangeSource.SOCIAL,
                reason=f"Успехи подшефного {mentorship.mentee.callsign or mentorship.mentee.username} за неделю",
                source_id=source_id,
            )
            grant_coins_with_daily_cap(mentor, int(reward))
        if applied:
            paid += 1
            points += Decimal(applied)
            events.mentor_rewarded(mentorship, applied)
    return {"week": week_key, "mentors_paid": paid, "points": float(points)}


def respects_received_count(user, days: int = 30) -> int:
    """Сколько респектов получил студент за период — для профиля."""
    since = timezone.now() - timedelta(days=days)
    return user.respects_received.filter(created_at__gte=since).count()
