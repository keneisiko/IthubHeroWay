"""
Пересчёт рейтинга по данным LXPSnapshot (v1): темы/КТ и флаг посещаемости searchStudents.

Эвристики статусов тем задокументированы в docs/RATING_FROM_LXP.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.integrations.models import LXPSnapshot
from apps.progress.models import RatingChangeSource, RatingLog

logger = logging.getLogger(__name__)


def _unwrap_category(block: dict | None) -> dict:
    if isinstance(block, dict) and "data" in block:
        inner = block.get("data")
        return inner if isinstance(inner, dict) else {}
    return block if isinstance(block, dict) else {}


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


@dataclass(frozen=True)
class LxpRatingApplyResult:
    snapshot_date: date
    users_considered: int
    users_updated: int
    partial_snapshot: bool
    notes: str


def apply_rating_from_lxp_snapshot(
    snapshot_date: date,
    *,
    snapshot_row: LXPSnapshot | None = None,
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
    ct_data = _unwrap_category(raw.get("control_points"))

    att_block = raw.get("attendance")
    att_data = _unwrap_category(att_block if isinstance(att_block, dict) else {})

    ct_pos_cap = int(limits.get("LXP_SNAPSHOT_CT_POSITIVE_CAP", 40))
    ct_neg_cap = int(limits.get("LXP_SNAPSHOT_CT_NEGATIVE_CAP", 60))
    abs_cap = int(limits.get("LXP_SNAPSHOT_ABSENCE_CAP", 10))

    block_thr = int(limits.get("CT_UNCLOSED_BLOCK_THRESHOLD", 2))
    max_when_blocked = int(limits.get("MAX_RATING_WHEN_BLOCKED", 399))

    ct_on = int(kp.get("CT_ON_TIME", 20))
    ct_miss = int(kp.get("CT_NOT_SUBMITTED", -20))
    abs_unexcused = int(kp.get("ABSENCE_UNEXCUSED", -10))

    qs = User.objects.filter(
        telegram_link__is_active=True,
    ).exclude(Q(lxp_user_id__isnull=True) | Q(lxp_user_id=""))

    considered = 0
    updated = 0

    for user in qs.iterator(chunk_size=200):
        lxp_uid = (user.lxp_user_id or "").strip()
        if not lxp_uid:
            continue

        considered += 1

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

        delta = delta_ct + delta_att

        before = int(user.rating_current)
        rating_after = max(0, min(1000, before + delta))

        if unclosed_total >= block_thr:
            rating_after = min(rating_after, max_when_blocked)

        if rating_after == before and unclosed_total == user.unclosed_ct_count:
            continue

        reason_parts = [
            f"LXP {snapshot_date.isoformat()}",
            f"Δ={delta}",
            f"topics_closed={closed_topics}/open={open_topics}",
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
            updated += 1

    notes = f"control_points_ok={ct_ok} partial_meta={partial}"
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
