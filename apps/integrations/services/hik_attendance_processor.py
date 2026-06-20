"""
Нормализация событий HikCentral и выпуск записей во внутреннюю очередь (ExternalEvent).

При наличии расписания отряда вычисляет опоздание относительно первой пары дня
и применяет штраф к рейтингу.
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
from apps.progress.models import RatingChangeSource, RatingLog
from apps.progress.services.late_penalties import late_penalty_delta
from apps.progress.services.rewards import apply_rating_delta_with_cap
from apps.schedule.services import classify_entrance_against_schedule

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


def _apply_late_penalty_if_needed(user, *, event_id: str, late_minutes: int) -> None:
    if late_minutes <= 0:
        return
    source_id = f"hik-late:{event_id}"
    if RatingLog.objects.filter(user=user, source_id=source_id).exists():
        return
    delta = late_penalty_delta(late_minutes)
    apply_rating_delta_with_cap(
        user=user,
        delta=delta,
        source=RatingChangeSource.SYSTEM,
        reason=f"Опоздание {late_minutes} мин (Hik)",
        source_id=source_id,
    )


def process_unprocessed_hik_events(*, limit: int = 5000) -> tuple[int, int, int]:
    """
    Для необработанных HikEvent с известным пользователем создаёт ExternalEvent (source=hik)
    и при опоздании — штраф рейтинга.

    Возвращает (рассмотрено, создано external, пропущено без карты).
    """
    User = get_user_model()
    pending = list(
        HikEvent.objects.filter(processed=False).order_by("event_time")[:limit]
    )
    seen = 0
    ext_created = 0
    skipped_no_user = 0
    process_errors = 0

    code_to_user: dict[str, User] = {}
    qs = User.objects.filter(
        (Q(hik_card_code__isnull=False) & ~Q(hik_card_code=""))
        | (Q(hik_person_id__isnull=False) & ~Q(hik_person_id=""))
    ).select_related("squad").only("id", "hik_card_code", "hik_person_id", "squad_id", "rating_current", "unclosed_ct_count")
    for u in qs.iterator(chunk_size=500):
        if u.hik_card_code:
            code_to_user[str(u.hik_card_code).strip()] = u
        if u.hik_person_id:
            pid = str(u.hik_person_id).strip()
            code_to_user.setdefault(pid, u)

    for he in pending:
        seen += 1
        code = (he.student_code or "").strip()
        if not code:
            skipped_no_user += 1
            continue
        user = code_to_user.get(code)
        if user is None:
            skipped_no_user += 1
            continue
        try:
            with transaction.atomic():
                classification = classify_entrance_against_schedule(
                    squad_id=user.squad_id,
                    event_dt=he.event_time,
                )
                event_type = classification["event_type"]
                late_minutes = classification.get("late_minutes")

                _, ext_c = ExternalEvent.objects.get_or_create(
                    source="hik",
                    external_event_id=he.event_id,
                    defaults={
                        "payload": {
                            "event_type": event_type,
                            "kind": "turnstile_pass",
                            "user_id": user.pk,
                            "student_code": code,
                            "door_name": he.door_name,
                            "hik_event_type": he.event_type,
                            "event_time": he.event_time.isoformat(),
                            "late_minutes": late_minutes,
                            "schedule_id": classification.get("schedule_id"),
                        },
                    },
                )
                if ext_c:
                    ext_created += 1
                if event_type == "late" and late_minutes is not None:
                    _apply_late_penalty_if_needed(user, event_id=he.event_id, late_minutes=int(late_minutes))
                HikEvent.objects.filter(pk=he.pk).update(processed=True)
        except Exception:
            process_errors += 1
            logger.exception("HikEvent process failed id=%s", he.pk)

    if process_errors > 0:
        from apps.integrations.services.telegram_alert import send_alert_to_admin

        send_alert_to_admin(
            title="Ошибки обработки событий Hik-Connect",
            message=f"Не удалось обработать {process_errors} из {seen} событий (см. логи приложения).",
            error_type="hik",
            deduplicate_key="hik_process_errors",
            is_critical=False,
        )
    return seen, ext_created, skipped_no_user
