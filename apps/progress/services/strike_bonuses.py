"""Бонусы за серии посещаемости и отсутствие опозданий.

Посещаемость считается по проходам турникета за конкретный день. Раньше
источником был флаг `hasAttendance` из LXP — он приходит без привязки к дате
и означает «у студента вообще есть посещаемость», поэтому серия росла каждый
день сама собой, а бонус за неделю без пропусков выдавался всем автоматически.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.integrations.models import ExternalEvent
from apps.progress.models import RatingChangeSource, RatingLog, UserStrike
from apps.progress.services.late_penalties import (
    attendance_streak_bonus_for_days,
    attendance_streak_milestone,
    late_streak_bonus_for_days,
    late_streak_milestone,
)
from apps.progress.services.rewards import apply_rating_delta_with_cap
from apps.schedule.models import Schedule

logger = logging.getLogger(__name__)


def users_present_on_date(day: date) -> set[int]:
    """Кто был в здании в этот день — по любому проходу через турникет."""
    return set(
        ExternalEvent.objects.filter(source="hik", event_date=day, user__isnull=False)
        .values_list("user_id", flat=True)
    )


def hik_has_data_for_date(day: date) -> bool:
    """Были ли вообще данные Hik за этот день.

    Если выгрузка не приехала (портал недоступен, каникулы, сбой Playwright),
    отсутствие проходов не означает, что все прогуляли. В такой день серии
    не трогаем вовсе.
    """
    return ExternalEvent.objects.filter(source="hik", event_date=day).exists()


def _has_classes(user: User, day: date) -> bool:
    """Были ли у отряда пары в этот день недели.

    Выходные и дни без расписания не должны рвать серию: студент не обязан
    приходить в колледж, когда занятий нет.
    """
    if not user.squad_id:
        return False
    return Schedule.objects.filter(
        squad_id=user.squad_id, day_of_week=day.weekday(), is_active=True
    ).exists()


def users_with_late_on_date(day: date) -> set[int]:
    """Кто опоздал в указанный день — одним запросом на весь прогон.

    Раньше здесь была проверка на одного пользователя, которая выбирала все
    его события за всю историю и фильтровала их в Python. Вызывалась она
    в цикле по всем агентам, то есть на каждый запуск задачи приходились
    сотни полных проходов по таблице событий.
    """
    return set(
        ExternalEvent.objects.filter(
            source="hik", event_type="late", event_date=day, user__isnull=False
        ).values_list("user_id", flat=True)
    )


def _streak_start(last_date: date | None, streak_days: int) -> date | None:
    """День начала текущей серии — часть ключа начисления.

    Благодаря нему веха «7 дней» выдаётся один раз за серию, но после обрыва
    и новой серии её можно заработать снова.
    """
    if not last_date or streak_days <= 0:
        return None
    return last_date - timedelta(days=streak_days - 1)


def _rating_already_applied(user_id: int, source_id: str) -> bool:
    return RatingLog.objects.filter(user_id=user_id, source_id=source_id).exists()


@transaction.atomic
def _apply_bonus_once(user: User, delta: int, source_id: str, reason: str) -> bool:
    if delta <= 0 or _rating_already_applied(user.pk, source_id):
        return False
    apply_rating_delta_with_cap(
        user=user,
        delta=delta,
        source=RatingChangeSource.SYSTEM,
        reason=reason[:250],
        source_id=source_id,
    )
    return True


def apply_strike_bonuses(current_date: date | None = None) -> dict:
    """Обновить серии и выдать бонусы за 7/14/21 день без опозданий и без пропусков.

    День учитывается, только если по нему есть данные Hik и у отряда в этот
    день были пары. Иначе выходные, каникулы и сбои выгрузки рвали бы серии.
    """
    # localdate(), а не date.today(): задача стоит на 23:30 по Москве, а сервер
    # живёт в UTC — там ещё предыдущие сутки, и «вчера» уезжало на два дня назад,
    # из-за чего серии рвались систематически.
    today = current_date or timezone.localdate()
    yesterday = today - timedelta(days=1)

    if not hik_has_data_for_date(yesterday):
        logger.info("strike_bonuses date=%s: нет данных Hik за %s, серии не трогаем", today, yesterday)
        return {
            "date": today.isoformat(),
            "strikes_updated": 0,
            "bonuses_applied": 0,
            "skipped": "no_hik_data",
        }

    late_user_ids = users_with_late_on_date(yesterday)
    present_user_ids = users_present_on_date(yesterday)

    users = User.objects.filter(telegram_link__is_active=True).select_related("squad")

    updated_strikes = 0
    bonuses = 0
    skipped_no_classes = 0

    for user in users.iterator(chunk_size=200):
        if not _has_classes(user, yesterday):
            skipped_no_classes += 1
            continue

        strike, _ = UserStrike.objects.get_or_create(user=user)
        was_present = user.pk in present_user_ids

        if was_present:
            if strike.last_attendance_date and strike.last_attendance_date == yesterday - timedelta(days=1):
                strike.attendance_strike += 1
            elif strike.last_attendance_date != yesterday:
                strike.attendance_strike = 1
            strike.last_attendance_date = yesterday
        else:
            strike.attendance_strike = 0
            strike.last_attendance_date = yesterday

        had_late = user.pk in late_user_ids
        if had_late:
            strike.late_strike = 0
            strike.last_late_date = yesterday
        elif was_present:
            if strike.last_late_date and strike.last_late_date == yesterday - timedelta(days=1):
                strike.late_strike += 1
            elif strike.last_late_date != yesterday:
                strike.late_strike = 1
            strike.last_late_date = yesterday

        strike.save(
            update_fields=[
                "attendance_strike",
                "late_strike",
                "last_attendance_date",
                "last_late_date",
                "updated_at",
            ]
        )
        updated_strikes += 1

        # Ключ начисления — «веха + начало серии», а не «число дней + дата».
        # Со старым ключом бонус за диапазон 7–13 дней получался заново каждый
        # день: ключ менялся, а награда оставалась той же (+5 ежедневно).
        late_milestone = late_streak_milestone(strike.late_strike)
        late_start = _streak_start(strike.last_late_date, strike.late_strike)
        if late_milestone and late_start:
            late_bonus = late_streak_bonus_for_days(strike.late_strike)
            if late_bonus and _apply_bonus_once(
                user,
                late_bonus,
                f"late_streak:{late_milestone}:{late_start.isoformat()}",
                f"Бонус за {late_milestone} дн. без опозданий",
            ):
                bonuses += 1

        att_milestone = attendance_streak_milestone(strike.attendance_strike)
        att_start = _streak_start(strike.last_attendance_date, strike.attendance_strike)
        if att_milestone and att_start:
            att_bonus = attendance_streak_bonus_for_days(strike.attendance_strike)
            if att_bonus and _apply_bonus_once(
                user,
                att_bonus,
                f"attendance_streak:{att_milestone}:{att_start.isoformat()}",
                f"Бонус за {att_milestone} дн. без пропусков",
            ):
                bonuses += 1

    logger.info("strike_bonuses date=%s strikes=%s bonuses=%s", today, updated_strikes, bonuses)
    return {
        "date": today.isoformat(),
        "strikes_updated": updated_strikes,
        "bonuses_applied": bonuses,
        "skipped_no_classes": skipped_no_classes,
    }
