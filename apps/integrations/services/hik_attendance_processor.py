"""
Нормализация событий HikCentral и выпуск записей во внутреннюю очередь (ExternalEvent).

Расписание занятий и расчёт «опоздание vs начало пары» — отдельный этап: поля late_minutes
заполняются позже или через интеграцию расписания (LXP / локальная модель).
"""

from __future__ import annotations

import logging
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.integrations.models import ExternalEvent, HikEvent

logger = logging.getLogger(__name__)


def parse_hik_event_time(value) -> datetime:
    if value is None:
        return timezone.now()
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            return parse_hik_event_time(int(s))
        dt = parse_datetime(s.replace("Z", "+00:00"))
        if dt:
            if timezone.is_naive(dt):
                return timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
    return timezone.now()


def student_code_from_row(row: dict) -> str:
    return str(
        row.get("personCode")
        or row.get("personNo")
        or row.get("cardNo")
        or row.get("cardNumber")
        or row.get("employeeNo")
        or row.get("personId")
        or ""
    ).strip()


def event_id_from_row(row: dict) -> str:
    for k in ("eventId", "event_id", "id", "recordId", "uuid"):
        v = row.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def door_name_from_row(row: dict) -> str:
    return str(
        row.get("doorName")
        or row.get("door_name")
        or row.get("doorIndexName")
        or row.get("deviceName")
        or ""
    )[:200]


def event_type_from_row(row: dict) -> str:
    return str(
        row.get("eventType")
        or row.get("eventName")
        or row.get("eventSubType")
        or row.get("mainEventType")
        or "access"
    )[:50]


def time_value_from_row(row: dict):
    return (
        row.get("eventTime")
        or row.get("event_time")
        or row.get("happenTime")
        or row.get("recvTime")
        or row.get("time")
    )


def save_hik_row_as_event(row: dict) -> tuple[HikEvent | None, bool]:
    """
    Создаёт HikEvent из сырой строки API. Возвращает (instance, created).
    """
    eid = event_id_from_row(row)
    if not eid:
        logger.debug("Hik row skipped: no event id in %s", row)
        return None, False
    code = student_code_from_row(row)
    ev_time = parse_hik_event_time(time_value_from_row(row))
    et = event_type_from_row(row)
    door = door_name_from_row(row)
    obj, created = HikEvent.objects.get_or_create(
        event_id=eid,
        defaults={
            "student_code": code,
            "event_time": ev_time,
            "event_type": et,
            "door_name": door,
            "raw_data": row,
        },
    )
    return obj, created


def process_unprocessed_hik_events(*, limit: int = 5000) -> tuple[int, int, int]:
    """
    Для необработанных HikEvent с известным пользователем создаёт ExternalEvent (source=hik).

    Возвращает (рассмотрено, создано external, пропущено без карты).
    """
    User = get_user_model()
    pending = list(
        HikEvent.objects.filter(processed=False).order_by("event_time")[:limit]
    )
    seen = 0
    ext_created = 0
    skipped_no_user = 0

    code_to_user: dict[str, int] = {}
    qs = User.objects.filter(
        (Q(hik_card_code__isnull=False) & ~Q(hik_card_code=""))
        | (Q(hik_person_id__isnull=False) & ~Q(hik_person_id=""))
    ).only("id", "hik_card_code", "hik_person_id")
    for u in qs.iterator(chunk_size=500):
        if u.hik_card_code:
            code_to_user[str(u.hik_card_code).strip()] = u.pk
        if u.hik_person_id:
            pid = str(u.hik_person_id).strip()
            code_to_user.setdefault(pid, u.pk)

    for he in pending:
        seen += 1
        code = (he.student_code or "").strip()
        if not code:
            skipped_no_user += 1
            continue
        uid = code_to_user.get(code) if code else None
        if uid is None:
            skipped_no_user += 1
            continue
        try:
            with transaction.atomic():
                _, ext_c = ExternalEvent.objects.get_or_create(
                    source="hik",
                    external_event_id=he.event_id,
                    defaults={
                        "payload": {
                            "event_type": "access",
                            "kind": "turnstile_pass",
                            "user_id": uid,
                            "student_code": code,
                            "door_name": he.door_name,
                            "hik_event_type": he.event_type,
                            "event_time": he.event_time.isoformat(),
                            "late_minutes": None,
                        },
                    },
                )
                if ext_c:
                    ext_created += 1
                HikEvent.objects.filter(pk=he.pk).update(processed=True)
        except Exception:
            logger.exception("HikEvent process failed id=%s", he.pk)
    return seen, ext_created, skipped_no_user
