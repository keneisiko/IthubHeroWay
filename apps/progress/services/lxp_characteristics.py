"""Опоры «Мощность» и «Ритм» из снимка LXP."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from apps.integrations.models import LXPSnapshot
from apps.progress.models import Characteristic, CharacteristicHistory
from apps.integrations.services.lxp_snapshot_format import unwrap_category

PILLAR_POWER = "power"
PILLAR_RHYTHM = "rhythm"
LXP_PILLARS = (PILLAR_POWER, PILLAR_RHYTHM)

DEFAULT_MAX_GRADE = 5.0


def compute_power_from_grades(lxp_uid: str, snapshot_data: dict, *, max_grade: float = DEFAULT_MAX_GRADE) -> float | None:
    grades = unwrap_category(snapshot_data.get("grades"))
    per_user = grades.get(lxp_uid)
    if not isinstance(per_user, dict) or not per_user:
        return None

    total = 0.0
    count = 0
    for _, disc in per_user.items():
        if not isinstance(disc, dict):
            continue
        raw = disc.get("disciplineGrade")
        if raw is None:
            raw = disc.get("disciplineGrade_V2")
        if raw is None:
            continue
        try:
            total += float(raw)
            count += 1
        except (TypeError, ValueError):
            continue

    if count == 0 or max_grade <= 0:
        return None

    avg = total / count
    normalized = min(avg / max_grade * 20.0, 20.0)
    return max(1.0, round(normalized, 2))


def compute_rhythm_from_attendance(lxp_uid: str, snapshot_data: dict) -> float | None:
    att = unwrap_category(snapshot_data.get("attendance"))
    row = att.get(lxp_uid)
    if not isinstance(row, dict):
        return None

    by_disc = row.get("by_discipline") or {}
    percentages: list[float] = []
    if isinstance(by_disc, dict):
        for _, data in by_disc.items():
            if not isinstance(data, dict):
                continue
            visited = data.get("visited")
            total = data.get("total")
            if total and int(total) > 0:
                try:
                    percentages.append(float(visited or 0) / float(total) * 100.0)
                except (TypeError, ValueError):
                    continue

    if not percentages:
        pct = row.get("percent")
        if pct is not None:
            try:
                percentages.append(float(pct))
            except (TypeError, ValueError):
                return None
        elif row.get("has_attendance") is True:
            return 20.0
        elif row.get("has_attendance") is False:
            return 1.0
        else:
            return None

    avg_percent = sum(percentages) / len(percentages)
    return max(1.0, min(20.0, round(avg_percent / 100.0 * 20.0, 2)))


def _save_pillar(user, pillar: str, value: float, formula_version: str) -> None:
    char_obj, _ = Characteristic.objects.get_or_create(user=user, pillar=pillar)
    char_obj.current = value
    char_obj.peak = max(char_obj.peak, value)
    char_obj.save(update_fields=["current", "peak", "last_updated"])
    CharacteristicHistory.objects.create(
        characteristic=char_obj,
        value=value,
        formula_version=formula_version,
    )


def update_lxp_pillars_from_snapshot(snapshot: LXPSnapshot | None = None) -> int:
    """Пересчёт опор power/rhythm по последнему (или указанному) снимку LXP."""
    snap = snapshot or LXPSnapshot.objects.order_by("-date").first()
    if not snap:
        return 0

    data = snap.data or {}
    User = get_user_model()
    updated = 0
    qs = User.objects.exclude(lxp_user_id__isnull=True).exclude(lxp_user_id="").only("id", "lxp_user_id")

    for user in qs.iterator(chunk_size=200):
        lxp_uid = (user.lxp_user_id or "").strip()
        if not lxp_uid:
            continue
        power = compute_power_from_grades(lxp_uid, data)
        rhythm = compute_rhythm_from_attendance(lxp_uid, data)
        if power is not None:
            _save_pillar(user, PILLAR_POWER, power, "lxp_v2")
            updated += 1
        if rhythm is not None:
            _save_pillar(user, PILLAR_RHYTHM, rhythm, "lxp_v2")
            updated += 1

    return updated
