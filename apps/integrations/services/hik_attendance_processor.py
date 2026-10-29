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
from django.db.models.fields.json import KT
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.integrations.models import ExternalEvent, HikEvent
from apps.integrations.services.hik_web_client import DIRECTION_ENTRY
from apps.schedule.services import classify_entrance_against_schedule

logger = logging.getLogger(__name__)

# Сколько раз пытаемся обработать событие, прежде чем увести его в карантин.
MAX_PROCESS_ATTEMPTS = 3

# Сколько событий с причиной показываем в Telegram-оповещении.
ALERT_ERROR_SAMPLES = 3


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


# Штрафа за опоздание нет: Положение (раздел 9) списывает только за
# пропущенную пару. Опоздание сохраняется в событии и используется квестами.


def format_hik_error_message(errors: int, seen: int, quarantined: int, samples: list[str]) -> str:
    """Текст оповещения: сколько событий упало и почему, без похода в логи."""
    lines = [f"Не удалось обработать {errors} из {seen} событий."]
    if quarantined:
        lines.append(f"В карантин ушло: {quarantined} (после {MAX_PROCESS_ATTEMPTS} попыток).")
    lines.extend(samples)
    if errors > len(samples):
        lines.append(f"...и ещё {errors - len(samples)}. Причина каждого — в HikEvent.last_error.")
    return "\n".join(lines)


def _revive_events_of_known_people(codes, emails) -> int:
    """Вернуть в очередь ничьи события, владелец которых теперь известен.

    Студенту выдали пропуск или связали его с Hik уже после прохода —
    прошлые проходы должны засчитаться, а не остаться помеченными навсегда.
    Почту сравниваем без учёта регистра: портал отдаёт её как есть.
    """
    codes, emails = list(codes), list(emails)
    if not codes and not emails:
        return 0
    ids = list(
        HikEvent.objects.filter(unmatched=True)
        .annotate(person_email=Lower(KT("raw_data__personEmail")))
        .filter(Q(student_code__in=codes) | Q(person_email__in=emails))
        .values_list("pk", flat=True)
    )
    if not ids:
        return 0
    return HikEvent.objects.filter(pk__in=ids).update(unmatched=False)


def process_unprocessed_hik_events(*, limit: int = 5000) -> tuple[int, int, int]:
    """
    Для необработанных HikEvent с известным пользователем создаёт ExternalEvent (source=hik)
    и при опоздании — штраф рейтинга.

    Возвращает (рассмотрено, создано external, пропущено без карты).
    """
    User = get_user_model()
    seen = 0
    ext_created = 0
    skipped_no_user = 0
    process_errors = 0
    error_samples: list[str] = []
    quarantined_count = 0

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

    revived = _revive_events_of_known_people(code_to_user.keys(), email_to_user.keys())
    if revived:
        logger.info("Hik: %s событий без студента теперь сопоставимы — вернул в очередь", revived)

    # Ничьи события в очередь не берём: при лимите 5000 их было 4931, и на
    # свежие проходы оставалось 69 мест за прогон.
    pending = list(
        HikEvent.objects.filter(processed=False, unmatched=False).order_by("event_time")[:limit]
    )
    unmatched_ids: list[int] = []

    # Первый вход за день решает, опоздал студент или нет. Прежде опозданием
    # считался каждый проход после начала пары: вернулся с обеда — «опоздание
    # 233 минуты». За две недели так набралось 114 опозданий на 8 обычных
    # проходов, то есть вся группа числилась опаздывающей.
    days_with_entry = {
        (row["user_id"], row["event_date"])
        for row in ExternalEvent.objects.filter(
            source="hik", event_type__in=("access", "late"), user__isnull=False
        ).values("user_id", "event_date")
    }

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
            unmatched_ids.append(he.pk)
            continue
        # direction: 1 — вход, 2 — выход (проверено на данных портала).
        # У старых выгрузок XLSX поля нет — там считаем проход входом,
        # чтобы не потерять историю.
        direction = raw.get("direction")
        is_entry = direction is None or direction == DIRECTION_ENTRY

        try:
            with transaction.atomic():
                event_date = timezone.localtime(he.event_time).date()
                day_key = (user.pk, event_date)
                first_entry_of_day = is_entry and day_key not in days_with_entry

                if first_entry_of_day:
                    classification = classify_entrance_against_schedule(
                        squad_id=user.squad_id,
                        event_dt=he.event_time,
                    )
                    event_type = classification["event_type"]
                    late_minutes = classification.get("late_minutes")
                    if event_type in ("access", "late"):
                        days_with_entry.add(day_key)
                else:
                    # Повторный проход и любой выход: к опозданию отношения
                    # не имеют, но сохраняем как присутствие.
                    classification = {"schedule_id": None}
                    event_type = "access"
                    late_minutes = None

                _, ext_c = ExternalEvent.objects.get_or_create(
                    source="hik",
                    external_event_id=he.event_id,
                    defaults={
                        # Колонки дублируют часть payload ради индексов:
                        # выборки «события пользователя за день» иначе
                        # требуют перебора всей таблицы.
                        "user": user,
                        "event_date": event_date,
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
                            "first_entry_of_day": first_entry_of_day,
                        },
                    },
                )
                if ext_c:
                    ext_created += 1
                HikEvent.objects.filter(pk=he.pk).update(processed=True)
        except Exception as exc:
            process_errors += 1
            logger.exception("HikEvent process failed id=%s", he.pk)
            # Считаем попытки и после исчерпания лимита уводим событие
            # в карантин: помечаем обработанным с сохранённой ошибкой,
            # чтобы оно не блокировало очередь на каждом прогоне.
            attempts = he.process_attempts + 1
            quarantined = attempts >= MAX_PROCESS_ATTEMPTS
            quarantined_count += int(quarantined)
            if len(error_samples) < ALERT_ERROR_SAMPLES:
                error_samples.append(
                    f"id={he.pk} {str(he.event_id)[:24]} (попытка {attempts}/{MAX_PROCESS_ATTEMPTS}): "
                    f"{type(exc).__name__}: {str(exc)[:200]}"
                )
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

    if unmatched_ids:
        HikEvent.objects.filter(pk__in=unmatched_ids).update(unmatched=True)

    if process_errors > 0:
        from apps.integrations.services.telegram_alert import send_alert_to_admin

        send_alert_to_admin(
            title="Ошибки обработки событий Hik-Connect",
            message=format_hik_error_message(process_errors, seen, quarantined_count, error_samples),
            error_type="hik",
            deduplicate_key="hik_process_errors",
            is_critical=False,
        )
    return seen, ext_created, skipped_no_user
