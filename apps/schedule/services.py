"""Сопоставление прохода Hik с расписанием отряда."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.utils import timezone

from apps.schedule.models import Schedule
from apps.operations.services.platform_settings import platform_setting


def classify_entrance_against_schedule(
    *, squad_id: int | None, event_dt: datetime, grace_minutes: int | None = None
) -> dict:
    """
    Определяет тип события по первой паре дня.

    Returns:
        event_type: access | late | absent
        late_minutes: int | None
        schedule_id: int | None
    """
    if not squad_id:
        return {"event_type": "access", "late_minutes": None, "schedule_id": None}

    local = timezone.localtime(event_dt)
    day = local.weekday()
    entrance_time = local.time()

    slots = list(
        Schedule.objects.filter(squad_id=squad_id, day_of_week=day, is_active=True).order_by("start_time")
    )
    if not slots:
        return {"event_type": "access", "late_minutes": None, "schedule_id": None}

    first = slots[0]
    last = slots[-1]

    # Турникет срабатывает, пока студент идёт к аудитории: проход ровно
    # в минуту начала пары опозданием считать нечестно.
    if grace_minutes is None:
        grace_minutes = int(platform_setting("hik_late_grace_minutes"))
    start_dt = timezone.make_aware(
        datetime.combine(local.date(), first.start_time), timezone.get_current_timezone()
    )
    deadline = start_dt + timedelta(minutes=max(0, grace_minutes))

    if local <= deadline:
        return {"event_type": "access", "late_minutes": 0, "schedule_id": first.pk}

    if entrance_time <= last.end_time:
        late_minutes = max(0, int((local - start_dt).total_seconds() // 60))
        return {"event_type": "late", "late_minutes": late_minutes, "schedule_id": first.pk}

    return {"event_type": "absent", "late_minutes": None, "schedule_id": last.pk}
