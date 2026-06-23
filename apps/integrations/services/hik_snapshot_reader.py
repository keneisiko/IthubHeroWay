from __future__ import annotations

from datetime import date

from apps.integrations.models import HikSnapshot


class NoHikSnapshotAvailable(RuntimeError):
    pass


def get_latest_hik_snapshot(prefer_date: date | None = None) -> HikSnapshot:
    if prefer_date:
        snap = HikSnapshot.objects.filter(date=prefer_date).first()
        if snap:
            return snap
    snap = HikSnapshot.objects.order_by("-date").first()
    if not snap:
        raise NoHikSnapshotAvailable("No Hik snapshots available")
    return snap


def get_hik_events_block(snapshot: HikSnapshot) -> list[dict]:
    data = snapshot.data or {}
    events = data.get("events")
    if isinstance(events, list):
        return events
    return []
