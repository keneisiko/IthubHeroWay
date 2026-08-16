"""Бонусы за серии посещаемости и отсутствие опозданий."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.integrations.models import ExternalEvent, LXPSnapshot
from apps.integrations.services.lxp_snapshot_format import unwrap_category
from apps.progress.models import RatingChangeSource, RatingLog, UserStrike
from apps.progress.services.late_penalties import (
    attendance_streak_bonus_for_days,
    attendance_streak_milestone,
    late_streak_bonus_for_days,
    late_streak_milestone,
)
from apps.progress.services.rewards import apply_rating_delta_with_cap

logger = logging.getLogger(__name__)


def _attendance_ok_for_user(snapshot_data: dict, lxp_uid: str) -> bool | None:
    att = unwrap_category(snapshot_data.get("attendance"))
    row = att.get(lxp_uid)
    if not isinstance(row, dict):
        return None
    if row.get("has_attendance") is False:
        return False
    if row.get("has_attendance") is True:
        return True
    return None


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
    """
    Обновляет UserStrike и начисляет бонусы за 7/14/21 день без опозданий
    и за 7 дней без пропусков (по LXP + отсутствие late из Hik).
    """
    # localdate(), а не date.today(): задача стоит на 23:30 по Москве, а сервер
    # живёт в UTC — там ещё предыдущие сутки, и «вчера» уезжало на два дня назад,
    # из-за чего серии рвались систематически.
    today = current_date or timezone.localdate()
    yesterday = today - timedelta(days=1)

    late_user_ids = users_with_late_on_date(yesterday)

    snap = LXPSnapshot.objects.filter(date=yesterday).first()
    snap_data = (snap.data or {}) if snap else {}

    users = User.objects.filter(
        telegram_link__is_active=True,
    ).exclude(Q(lxp_user_id__isnull=True) | Q(lxp_user_id=""))

    updated_strikes = 0
    bonuses = 0

    for user in users.iterator(chunk_size=200):
        lxp_uid = (user.lxp_user_id or "").strip()
        strike, _ = UserStrike.objects.get_or_create(user=user)

        att_ok = _attendance_ok_for_user(snap_data, lxp_uid) if snap_data else None
        if att_ok is True:
            if strike.last_attendance_date and strike.last_attendance_date == yesterday - timedelta(days=1):
                strike.attendance_strike += 1
            elif strike.last_attendance_date != yesterday:
                strike.attendance_strike = 1
            strike.last_attendance_date = yesterday
        elif att_ok is False:
            strike.attendance_strike = 0
            strike.last_attendance_date = yesterday

        had_late = user.pk in late_user_ids
        if not had_late and snap_data:
            if strike.last_late_date and strike.last_late_date == yesterday - timedelta(days=1):
                strike.late_strike += 1
            elif strike.last_late_date != yesterday:
                strike.late_strike = 1
            strike.last_late_date = yesterday
        elif had_late:
            strike.late_strike = 0
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
    return {"date": today.isoformat(), "strikes_updated": updated_strikes, "bonuses_applied": bonuses}
