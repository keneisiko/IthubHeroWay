from __future__ import annotations

from datetime import date

from apps.integrations.models import LXPSnapshot
from apps.integrations.services.lxp_snapshot_format import unwrap_category


class NoSnapshotAvailable(RuntimeError):
    pass


def get_latest_snapshot(prefer_date: date | None = None) -> LXPSnapshot:
    if prefer_date:
        snap = LXPSnapshot.objects.filter(date=prefer_date).first()
        if snap:
            return snap
    snap = LXPSnapshot.objects.order_by("-date").first()
    if not snap:
        raise NoSnapshotAvailable("No LXP snapshots available")
    return snap


def get_student_attendance(user_id: int, prefer_date: date | None = None):
    snap = get_latest_snapshot(prefer_date=prefer_date)
    raw = (snap.data or {}).get("attendance")
    return unwrap_category(raw).get(str(user_id))


def get_student_ct(user_id: int, prefer_date: date | None = None):
    snap = get_latest_snapshot(prefer_date=prefer_date)
    raw = (snap.data or {}).get("control_points")
    return unwrap_category(raw).get(str(user_id))


def get_student_grades(user_id: int, prefer_date: date | None = None):
    snap = get_latest_snapshot(prefer_date=prefer_date)
    raw = (snap.data or {}).get("grades")
    return unwrap_category(raw).get(str(user_id))


def get_course_progress(course_id: str, prefer_date: date | None = None):
    snap = get_latest_snapshot(prefer_date=prefer_date)
    raw = (snap.data or {}).get("course_progress")
    return unwrap_category(raw).get(str(course_id))

