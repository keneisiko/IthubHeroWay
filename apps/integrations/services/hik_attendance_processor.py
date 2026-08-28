"""
Нормализация событий HikCentral и выпуск записей во внутреннюю очередь (ExternalEvent).

При наличии расписания отряда вычисляет опоздание относительно первой пары дня
и применяет штраф к рейтингу.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.integrations.models import ExternalEvent, HikEvent
from apps.integrations.services.hik_web_client import DIRECTION_ENTRY
from apps.progress.models import RatingChangeSource, RatingLog
from apps.progress.services.late_penalties import late_penalty_delta
from apps.progress.services.rewards import apply_rating_delta_with_cap
from apps.schedule.services import classify_entrance_against_schedule

logger = logging.getLogger(__name__)

# Сколько раз пытаемся обработать событие, прежде чем увести его в карантин.
MAX_PROCESS_ATTEMPTS = 3


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
        return datetime.fromtimestamp(ts, tz=UTC)
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


def late_penalty_source_id(user_id: int, event_dt: datetime) -> str:
    """Ключ штрафа за опоздание — один на пользователя в день.

    Раньше ключ строился по event_id, то есть штрафовался каждый проход
    турникета: вышел в перерыве и вернулся — ещё минус к рейтингу.
    Опоздание — событие дня, а не события прохода.
    """
    local_date = timezone.localtime(event_dt).date()
    return f"hik-late:{user_id}:{local_date.isoformat()}"


def _apply_late_penalty_if_needed(user, *, event_dt: datetime, late_minutes: int) -> None:
    if late_minutes <= 0:
        return

    source_id = late_penalty_source_id(user.pk, event_dt)

    # Блокировка строки пользователя закрывает гонку между воркерами: без неё
    # два параллельных обработчика проходят проверку exists() одновременно
    # и штрафуют дважды. Заодно рейтинг читается свежим, а не из кеша,
    # собранного в начале прогона.
    locked_user = get_user_model().objects.select_for_update().get(pk=user.pk)
    if RatingLog.objects.filter(user_id=locked_user.pk, source_id=source_id).exists():
        return

    delta = late_penalty_delta(late_minutes)
    apply_rating_delta_with_cap(
        user=locked_user,
        delta=delta,
        source=RatingChangeSource.SYSTEM,
        reason=f"Опоздание {late_minutes} мин (Hik)",
        source_id=source_id,
    )
    # Кеш пользователей в вызывающем коде держит ту же запись — синхронизируем,
    # чтобы последующие события в этом же прогоне считались от нового рейтинга.
    user.rating_current = locked_user.rating_current


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
    email_to_user: dict[str, User] = {}
    qs = (
        User.objects.filter(
            Q(hik_card_code__isnull=False) & ~Q(hik_card_code="")
            | Q(hik_person_id__isnull=False) & ~Q(hik_person_id="")
            | ~Q(email="")
        )
        .select_related("squad")
        .only(
            "id",
            "email",
            "hik_card_code",
            "hik_person_id",
            "squad_id",
            "rating_current",
            "unclosed_ct_count",
        )
    )
    for u in qs.iterator(chunk_size=500):
        if u.hik_card_code:
            code_to_user[str(u.hik_card_code).strip()] = u
        if u.hik_person_id:
            code_to_user.setdefault(str(u.hik_person_id).strip(), u)
        if u.email:
            email_to_user.setdefault(u.email.strip().lower(), u)

    for he in pending:
        seen += 1
        code = (he.student_code or "").strip()
        # Портал отдаёт cardNumber пустым во всех записях, зато в каждой есть
        # почта студента — она же приходит из LXP, поэтому связка получается
        # автоматической, без ручного проставления кодов карт в админке.
        raw = he.raw_data if isinstance(he.raw_data, dict) else {}
        email = str(raw.get("personEmail") or "").strip().lower()

        user = code_to_user.get(code) if code else None
        if user is None and email:
            user = email_to_user.get(email)
        if user is None:
            skipped_no_user += 1
            continue
        # direction: 1 — вход, 2 — выход (проверено на данных портала).
        # У старых выгрузок XLSX поля нет — там считаем проход входом,
        # чтобы не потерять историю.
        direction = raw.get("direction")
        is_entry = direction is None or direction == DIRECTION_ENTRY

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
                        # Колонки дублируют часть payload ради индексов:
                        # выборки «события пользователя за день» иначе
                        # требуют перебора всей таблицы.
                        "user": user,
                        "event_date": timezone.localtime(he.event_time).date(),
                        "event_type": event_type,
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
                            "direction": raw.get("direction"),
                            "is_entry": is_entry,
                        },
                    },
                )
                if ext_c:
                    ext_created += 1
                # Штрафуем только за вход: выход с занятий опозданием не является.
                if is_entry and event_type == "late" and late_minutes is not None:
                    _apply_late_penalty_if_needed(
                        user, event_dt=he.event_time, late_minutes=int(late_minutes)
                    )
                HikEvent.objects.filter(pk=he.pk).update(processed=True)
        except Exception as exc:
            process_errors += 1
            logger.exception("HikEvent process failed id=%s", he.pk)
            # Считаем попытки и после исчерпания лимита уводим событие
            # в карантин: помечаем обработанным с сохранённой ошибкой,
            # чтобы оно не блокировало очередь на каждом прогоне.
            attempts = he.process_attempts + 1
            quarantined = attempts >= MAX_PROCESS_ATTEMPTS
            HikEvent.objects.filter(pk=he.pk).update(
                process_attempts=attempts,
                last_error=f"{type(exc).__name__}: {exc}"[:1000],
                processed=quarantined,
            )
            if quarantined:
                logger.error(
                    "HikEvent id=%s отправлено в карантин после %s попыток",
                    he.pk,
                    attempts,
                )

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
