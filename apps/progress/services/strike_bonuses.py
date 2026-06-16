"""Бонусы за серии посещаемости и отсутствие опозданий."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.integrations.models import ExternalEvent, LXPSnapshot
from apps.progress.models import RatingChangeSource, RatingLog, UserStrike
from apps.progress.services.late_penalties import attendance_streak_bonus_for_days, late_streak_bonus_for_days
from apps.progress.services.rewards import apply_rating_delta_with_cap

logger = logging.getLogger(__name__)


def _unwrap_attendance(block: dict | None) -> dict:
    if isinstance(block, dict) and "data" in block:
        inner = block.get("data")
        return inner if isinstance(inner, dict) else {}
    return block if isinstance(block, dict) else {}


def _attendance_ok_for_user(snapshot_data: dict, lxp_uid: str) -> bool | None:
    att = _unwrap_attendance(snapshot_data.get("attendance"))
    row = att.get(lxp_uid)
    if not isinstance(row, dict):
        return None
    if row.get("has_attendance") is False:
        return False
    if row.get("has_attendance") is True:
        return True
    return None


def _had_late_on_date(user_id: int, day: date) -> bool:
    day_s = day.isoformat()
    qs = ExternalEvent.objects.filter(source="hik", payload__user_id=user_id)
    for ev in qs.only("payload").iterator(chunk_size=200):
        payload = ev.payload or {}
        if payload.get("event_type") != "late":
            continue
        et = payload.get("event_time") or ""
        if isinstance(et, str) and et.startswith(day_s):
            return True
    return False


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
    today = current_date or date.today()
    yesterday = today - timedelta(days=1)

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

        had_late = _had_late_on_date(user.pk, yesterday)
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

        late_bonus = late_streak_bonus_for_days(strike.late_strike)
        if late_bonus and _apply_bonus_once(
            user,
            late_bonus,
            f"late_streak_{strike.late_strike}:{today.isoformat()}",
            f"Бонус за {strike.late_strike} дн. без опозданий",
        ):
            bonuses += 1

        att_bonus = attendance_streak_bonus_for_days(strike.attendance_strike)
        if att_bonus and _apply_bonus_once(
            user,
            att_bonus,
            f"attendance_streak_{strike.attendance_strike}:{today.isoformat()}",
            f"Бонус за {strike.attendance_strike} дн. без пропусков",
        ):
            bonuses += 1

    logger.info("strike_bonuses date=%s strikes=%s bonuses=%s", today, updated_strikes, bonuses)
    return {"date": today.isoformat(), "strikes_updated": updated_strikes, "bonuses_applied": bonuses}
