"""Награды за социальные механики.

Коэффициенты `RESPECT_REWARD`, `MENTEE_WEEKLY_COINS` и `MENTORING` были
описаны в регламенте и заведены в настройках, но не начислялись нигде:
респект отправлялся «в пустоту», а наставник не получал ничего.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

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


@transaction.atomic
def grant_mentorship_start_bonus(mentorship: Mentorship) -> int:
    """Разовый рейтинг наставнику за взятого подшефного.

    Ключ включает подшефного: за каждого нового — один раз, повторное
    оформление той же пары ничего не добавляет.
    """
    drive = getattr(settings, "RATING_DRIVE", {})
    amount = int(drive.get("MENTORING", 15))
    if amount <= 0:
        return 0

    source_id = f"mentorship:{mentorship.mentee_id}"
    if RatingLog.objects.filter(user=mentorship.mentor, source_id=source_id).exists():
        return 0

    return apply_rating_delta_with_cap(
        user=mentorship.mentor,
        delta=amount,
        source=RatingChangeSource.SOCIAL,
        reason=f"Наставничество: {mentorship.mentee.callsign or mentorship.mentee.username}",
        source_id=source_id,
    )


def pay_mentors_weekly(now=None) -> dict:
    """Еженедельные монеты наставникам за активных подшефных.

    Начисления группируются по наставнику: если платить в цикле по записям
    наставничества, каждая из них несёт собственную копию пользователя,
    и вторая выплата перезаписывает баланс, посчитанный первой.

    Ключ начисления — наставник, подшефный и неделя: повторный запуск задачи
    (ретрай Celery, ручной прогон) ничего не удваивает.
    """
    now = now or timezone.now()
    iso_year, iso_week, _ = now.date().isocalendar()
    week_key = f"{iso_year}-W{iso_week:02d}"
    per_mentee = int(_rewards().get("MENTEE_WEEKLY_COINS", 2))
    if per_mentee <= 0:
        return {"week": week_key, "mentors_paid": 0, "coins_granted": 0}

    pending: dict[int, list] = {}
    active = (
        Mentorship.objects.filter(ended_at__isnull=True)
        .select_related("mentor", "mentee")
        .order_by("mentor_id")
    )
    for mentorship in active:
        source_id = f"mentorship_weekly:{mentorship.mentee_id}:{week_key}"
        if RatingLog.objects.filter(user_id=mentorship.mentor_id, source_id=source_id).exists():
            continue
        pending.setdefault(mentorship.mentor_id, []).append(mentorship)

    mentors_paid = 0
    coins_granted = 0
    User = get_user_model()
    for mentor_id, rows in pending.items():
        with transaction.atomic():
            mentor = User.objects.select_for_update().get(pk=mentor_id)
            granted = grant_coins_with_daily_cap(mentor, per_mentee * len(rows))
            for mentorship in rows:
                # Запись в журнал с нулевой дельтой — маркер выплаты: отдельной
                # таблицы под монеты в проекте нет, а без следа задача заплатила
                # бы второй раз при любом повторном запуске.
                RatingLog.objects.create(
                    user=mentor,
                    value_before=mentor.rating_current,
                    value_after=mentor.rating_current,
                    delta=0,
                    source=RatingChangeSource.SOCIAL,
                    source_id=f"mentorship_weekly:{mentorship.mentee_id}:{week_key}",
                    reason=f"Монеты наставнику за {mentorship.mentee.username}",
                )
            mentors_paid += len(rows)
            coins_granted += granted

    return {"week": week_key, "mentors_paid": mentors_paid, "coins_granted": coins_granted}


def respects_received_count(user, days: int = 30) -> int:
    """Сколько респектов получил студент за период — для профиля."""
    since = timezone.now() - timedelta(days=days)
    return user.respects_received.filter(created_at__gte=since).count()
