"""
Пересчёт рейтинга по данным LXPSnapshot (v1): темы/КТ и флаг посещаемости searchStudents.

Эвристики статусов тем задокументированы в docs/RATING_FROM_LXP.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.integrations.models import LXPSnapshot
from apps.integrations.services.lxp_snapshot_format import unwrap_category
from apps.progress.models import RatingChangeSource, RatingLog

logger = logging.getLogger(__name__)


def _topic_closed(status) -> bool:
    s = ("" if status is None else str(status)).strip().upper()
    if not s:
        return False
    markers = (
        "PASSED",
        "DONE",
        "SUCCESS",
        "ACCEPTED",
        "CLOSED",
        "COMPLETE",
        "ЗАЧТ",
        "СДАН",
        "APPROVED",
    )
    return any(m in s for m in markers)


def _collect_topic_counts(control_points_flat: dict) -> tuple[int, int]:
    closed_n = 0
    open_n = 0
    for _, disc_payload in control_points_flat.items():
        if not isinstance(disc_payload, dict):
            continue
        topics = disc_payload.get("topics") or []
        if not isinstance(topics, list):
            continue
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            st = topic.get("status")
            if _topic_closed(st):
                closed_n += 1
            else:
                open_n += 1
    return closed_n, open_n


def _attendance_row(snapshot_data: dict, lxp_uid: str) -> dict | None:
    att = unwrap_category(snapshot_data.get("attendance"))
    row = att.get(lxp_uid)
    return row if isinstance(row, dict) else None


def _full_week_attendance_bonus(lxp_uid: str, end_date: date) -> int:
    """+15 если за 7 календарных дней подряд has_attendance === true в снимках."""
    kp = getattr(settings, "RATING_KP", {})
    bonus = int(kp.get("ATTENDANCE_FULL_WEEK", 15))
    start = end_date - timedelta(days=6)
    snaps = LXPSnapshot.objects.filter(date__gte=start, date__lte=end_date).order_by("date")
    if snaps.count() < 7:
        return 0
    for snap in snaps:
        row = _attendance_row(snap.data or {}, lxp_uid)
        if not row or row.get("has_attendance") is not True:
            return 0
    return bonus


def _bonus_already_applied(user_id: int, source_id: str) -> bool:
    return RatingLog.objects.filter(user_id=user_id, source_id=source_id).exists()


@dataclass(frozen=True)
class LxpRatingApplyResult:
    snapshot_date: date
    users_considered: int
    users_updated: int
    partial_snapshot: bool
    notes: str


def _already_applied_user_ids(snapshot_date: date) -> set[int]:
    """Кому дельта за эту дату уже начислена.

    Основная дельта записывается с `source_id` = дата снимка. Без этой проверки
    повторный запуск за ту же дату (ретрай Celery, ручной прогон, повторная
    выгрузка снимка) начислял всё заново — рейтинг просто удваивался.
    """
    return set(
        RatingLog.objects.filter(source_id=snapshot_date.isoformat()).values_list(
            "user_id", flat=True
        )
    )


def apply_rating_from_lxp_snapshot(
    snapshot_date: date,
    *,
    snapshot_row: LXPSnapshot | None = None,
    force: bool = False,
) -> LxpRatingApplyResult:
    kp = getattr(settings, "RATING_KP", {})
    limits = getattr(settings, "RATING_LIMITS", {})

    snap = snapshot_row or LXPSnapshot.objects.filter(date=snapshot_date).first()
    if not snap:
        return LxpRatingApplyResult(
            snapshot_date=snapshot_date,
            users_considered=0,
            users_updated=0,
            partial_snapshot=False,
            notes="no_snapshot_row",
        )

    raw = snap.data or {}
    meta = raw.get("meta") or {}
    partial = bool(meta.get("partial"))

    ct_ok = bool((raw.get("control_points") or {}).get("ok")) if isinstance(raw.get("control_points"), dict) else False
    ct_data = unwrap_category(raw.get("control_points"))

    att_block = raw.get("attendance")
    att_data = unwrap_category(att_block if isinstance(att_block, dict) else {})

    ct_pos_cap = int(limits.get("LXP_SNAPSHOT_CT_POSITIVE_CAP", 40))
    ct_neg_cap = int(limits.get("LXP_SNAPSHOT_CT_NEGATIVE_CAP", 60))
    abs_cap = int(limits.get("LXP_SNAPSHOT_ABSENCE_CAP", 10))

    block_thr = int(limits.get("CT_UNCLOSED_BLOCK_THRESHOLD", 2))
    max_when_blocked = int(limits.get("MAX_RATING_WHEN_BLOCKED", 399))

    ct_on = int(kp.get("CT_ON_TIME", 20))
    ct_miss = int(kp.get("CT_NOT_SUBMITTED", -20))
    abs_unexcused = int(kp.get("ABSENCE_UNEXCUSED", -10))
    ct_all_bonus = int(kp.get("CT_ALL_CLOSED_BONUS", 30))

    qs = User.objects.filter(
        telegram_link__is_active=True,
    ).exclude(Q(lxp_user_id__isnull=True) | Q(lxp_user_id=""))

    considered = 0
    updated = 0
    skipped_already_applied = 0

    already_applied = set() if force else _already_applied_user_ids(snapshot_date)

    for user in qs.iterator(chunk_size=200):
        lxp_uid = (user.lxp_user_id or "").strip()
        if not lxp_uid:
            continue

        considered += 1

        if user.pk in already_applied:
            skipped_already_applied += 1
            continue

        closed_topics = 0
        open_topics = 0
        unclosed_total = int(user.unclosed_ct_count)
        delta_ct = 0

        if ct_ok:
            per_user = ct_data.get(lxp_uid)
            if isinstance(per_user, dict) and per_user:
                closed_topics, open_topics = _collect_topic_counts(per_user)
                unclosed_total = open_topics
                raw_pos = closed_topics * ct_on
                raw_neg = open_topics * ct_miss
                pos_applied = min(raw_pos, ct_pos_cap)
                neg_applied = max(raw_neg, -ct_neg_cap)
                delta_ct = pos_applied + neg_applied

        delta_att = 0
        row_att = att_data.get(lxp_uid)
        if isinstance(row_att, dict) and row_att.get("has_attendance") is False:
            delta_att = max(-abs_cap, abs_unexcused)

        delta_bonus = 0
        ct_bonus = 0
        week_bonus = 0
        ct_source = f"ct_all_closed:{snapshot_date.isoformat()}"
        week_start = snapshot_date - timedelta(days=6)
        week_source = f"attendance_full_week:{week_start.isoformat()}"

        if ct_ok and open_topics == 0 and closed_topics > 0 and not _bonus_already_applied(user.pk, ct_source):
            ct_bonus = ct_all_bonus
        if not _bonus_already_applied(user.pk, week_source):
            week_bonus = _full_week_attendance_bonus(lxp_uid, snapshot_date)
        delta_bonus = ct_bonus + week_bonus

        delta = delta_ct + delta_att + delta_bonus

        before = int(user.rating_current)
        rating_after = max(0, min(1000, before + delta))

        if unclosed_total >= block_thr:
            rating_after = min(rating_after, max_when_blocked)

        if (
            rating_after == before
            and unclosed_total == user.unclosed_ct_count
            and delta_bonus == 0
        ):
            continue

        reason_parts = [
            f"LXP {snapshot_date.isoformat()}",
            f"Δ={delta}",
            f"topics_closed={closed_topics}/open={open_topics}",
            f"bonus={delta_bonus}",
            f"partial={partial}",
        ]
        reason = "; ".join(reason_parts)[:250]

        with transaction.atomic():
            u = User.objects.select_for_update().get(pk=user.pk)
            u.unclosed_ct_count = min(unclosed_total, 65535)
            u.rating_current = rating_after
            u.save(update_fields=["unclosed_ct_count", "rating_current"])
            RatingLog.objects.create(
                user=u,
                value_before=before,
                value_after=rating_after,
                delta=rating_after - before,
                source=RatingChangeSource.SYSTEM,
                source_id=snapshot_date.isoformat(),
                reason=reason,
            )
            if ct_bonus:
                RatingLog.objects.get_or_create(
                    user=u,
                    source_id=ct_source,
                    defaults={
                        "value_before": rating_after,
                        "value_after": rating_after,
                        "delta": 0,
                        "source": RatingChangeSource.SYSTEM,
                        "reason": "Маркер: все КТ закрыты",
                    },
                )
            if week_bonus:
                RatingLog.objects.get_or_create(
                    user=u,
                    source_id=week_source,
                    defaults={
                        "value_before": rating_after,
                        "value_after": rating_after,
                        "delta": 0,
                        "source": RatingChangeSource.SYSTEM,
                        "reason": "Маркер: неделя без пропусков",
                    },
                )
            updated += 1

    notes = (
        f"control_points_ok={ct_ok} partial_meta={partial} "
        f"already_applied={skipped_already_applied}"
    )
    logger.info(
        "lxp_rating_apply date=%s considered=%s updated=%s %s",
        snapshot_date,
        considered,
        updated,
        notes,
    )

    return LxpRatingApplyResult(
        snapshot_date=snapshot_date,
        users_considered=considered,
        users_updated=updated,
        partial_snapshot=partial,
        notes=notes,
    )
