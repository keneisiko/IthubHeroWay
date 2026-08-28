"""Quest condition evaluators backed by Hik, LXP, YouGile integrations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from django.utils import timezone

from apps.accounts.models import User
from apps.integrations.models import ExternalEvent
from apps.integrations.services.lxp_snapshot_reader import get_student_attendance, get_student_ct
from apps.progress.models import UserStrike
from apps.progress.services.ct_status import is_topic_closed
from apps.quests.models import QuestVerifierKind
from apps.schedule.models import Schedule


@dataclass
class VerificationResult:
    completed: bool
    progress: float
    evidence: dict[str, Any]
    message: str = ""


# Определение «КТ закрыта» одно на весь проект: рейтинг и квесты обязаны
# сходиться, иначе студент видит начисление за КТ и невыполненный квест
# «закрой КТ» одновременно.


def _hik_events_for_user_on_date(user_id: int, day: date) -> list[dict]:
    """События Hik пользователя за день.

    Раньше здесь перебиралась вся таблица `ExternalEvent` в Python — и так
    для каждого пользователя и каждого проверяемого дня. При нескольких сотнях
    студентов и недельном квесте это давало сотни тысяч итераций на прогон.
    Теперь фильтрация идёт в БД по индексу (user, event_date).
    """
    return [
        ev.payload or {}
        for ev in ExternalEvent.objects.filter(
            source="hik", user_id=user_id, event_date=day
        ).only("payload")
    ]


def _hik_events_for_user_in_range(user_id: int, start: date, end: date) -> dict[date, list[dict]]:
    """События за диапазон дат — одним запросом вместо запроса на каждый день."""
    events: dict[date, list[dict]] = {}
    queryset = ExternalEvent.objects.filter(
        source="hik", user_id=user_id, event_date__gte=start, event_date__lte=end
    ).only("payload", "event_date")
    for ev in queryset:
        events.setdefault(ev.event_date, []).append(ev.payload or {})
    return events


def _parse_event_time(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if timezone.is_aware(dt) else timezone.make_aware(dt)
        except ValueError:
            return None
    return None


def _checkin_deadline(user: User, params: dict, target_date: date) -> datetime:
    """Дедлайн утреннего чек-ина: начало первой пары отряда плюс запас.

    Раньше дедлайн был жёстко 10:00 для всех. Отряд второй смены, пришедший
    ровно к своей первой паре в 12:30, квест не выполнял — при том, что
    штрафы за опоздание считались по расписанию и опоздания у него не было.
    """
    grace_minutes = int(params.get("grace_minutes", 0))
    tz = timezone.get_current_timezone()

    first_slot = None
    if user.squad_id:
        first_slot = (
            Schedule.objects.filter(
                squad_id=user.squad_id, day_of_week=target_date.weekday(), is_active=True
            )
            .order_by("start_time")
            .first()
        )

    if first_slot:
        base = datetime.combine(target_date, first_slot.start_time)
    else:
        # Расписания нет — остаётся общий дедлайн из параметров шаблона.
        base = datetime.combine(
            target_date,
            time(int(params.get("deadline_hour", 10)), int(params.get("deadline_minute", 0))),
        )
    return timezone.make_aware(base, tz) + timedelta(minutes=grace_minutes)


def verify_hik_on_time(user: User, params: dict, target_date: date) -> VerificationResult:
    events = _hik_events_for_user_on_date(user.pk, target_date)
    deadline = _checkin_deadline(user, params, target_date)

    on_time = []
    late = []
    for ev in events:
        if ev.get("event_type") == "late":
            late.append(ev)
            continue
        if ev.get("event_type") != "access":
            continue
        late_minutes = ev.get("late_minutes")
        if late_minutes is not None and int(late_minutes) > 0:
            late.append(ev)
            continue
        event_dt = _parse_event_time(ev.get("event_time"))
        if event_dt and event_dt <= deadline:
            on_time.append(ev)

    if on_time:
        return VerificationResult(
            completed=True,
            progress=1.0,
            evidence={"verifier": QuestVerifierKind.HIK_ON_TIME, "date": target_date.isoformat(), "events": len(on_time)},
            message="Вход до дедлайна зафиксирован",
        )
    if late:
        return VerificationResult(
            completed=False,
            progress=0.0,
            evidence={"verifier": QuestVerifierKind.HIK_ON_TIME, "date": target_date.isoformat(), "late": True},
            message="Зафиксировано опоздание",
        )
    now = timezone.now()
    if target_date == now.date() and now < deadline:
        return VerificationResult(
            completed=False,
            progress=0.0,
            evidence={"verifier": QuestVerifierKind.HIK_ON_TIME, "date": target_date.isoformat(), "pending": True},
            message="Ожидание прохода до дедлайна",
        )
    return VerificationResult(
        completed=False,
        progress=0.0,
        evidence={"verifier": QuestVerifierKind.HIK_ON_TIME, "date": target_date.isoformat(), "no_events": True},
        message="Проход не зафиксирован",
    )


def verify_hik_no_late(user: User, params: dict, target_date: date) -> VerificationResult:
    days = int(params.get("days", 1))
    start = target_date - timedelta(days=days - 1)

    # Один запрос на весь период вместо запроса на каждый день.
    by_day = _hik_events_for_user_in_range(user.pk, start, target_date)

    late_days: list[str] = []
    checked = 0
    d = start
    while d <= target_date:
        events = by_day.get(d, [])
        if events:
            checked += 1
        if any(ev.get("event_type") == "late" for ev in events):
            late_days.append(d.isoformat())
        d += timedelta(days=1)

    if late_days:
        return VerificationResult(
            completed=False,
            progress=max(0.0, 1.0 - len(late_days) / max(days, 1)),
            evidence={"verifier": QuestVerifierKind.HIK_NO_LATE, "late_days": late_days},
            message="Есть опоздания в периоде",
        )
    if checked == 0 and target_date >= timezone.now().date():
        return VerificationResult(
            completed=False,
            progress=0.0,
            evidence={"verifier": QuestVerifierKind.HIK_NO_LATE, "pending": True},
            message="Ожидание данных Hik",
        )
    return VerificationResult(
        completed=True,
        progress=1.0,
        evidence={"verifier": QuestVerifierKind.HIK_NO_LATE, "days_checked": days},
        message="Без опозданий",
    )


def _attendance_percent(row: dict) -> float | None:
    """Средний процент посещаемости по дисциплинам из снимка."""
    by_discipline = row.get("by_discipline")
    if not isinstance(by_discipline, dict) or not by_discipline:
        return None
    visited_total = 0
    lessons_total = 0
    percents: list[float] = []
    for entry in by_discipline.values():
        if not isinstance(entry, dict):
            continue
        visited = entry.get("visited")
        total = entry.get("total")
        if isinstance(visited, (int, float)) and isinstance(total, (int, float)) and total > 0:
            visited_total += int(visited)
            lessons_total += int(total)
            continue
        percent = entry.get("percent")
        if isinstance(percent, (int, float)):
            percents.append(float(percent))
    if lessons_total > 0:
        return round(100.0 * visited_total / lessons_total, 1)
    if percents:
        return round(sum(percents) / len(percents), 1)
    return None


def verify_lxp_attendance(user: User, params: dict, target_date: date) -> VerificationResult:
    """Посещаемость по проценту занятий, а не по флагу «посещаемость есть».

    `hasAttendance` из searchStudents приходит без привязки к дате: это
    свойство студента за всё время обучения. Квест на нём выполнялся каждый
    период автоматически у всех, кто вообще ходит на пары.
    """
    if not user.lxp_user_id:
        return VerificationResult(
            completed=False,
            progress=0.0,
            evidence={"verifier": QuestVerifierKind.LXP_ATTENDANCE, "error": "no_lxp_user_id"},
            message="Нет привязки LXP",
        )

    min_percent = float(params.get("min_percent", 80))
    row = get_student_attendance(str(user.lxp_user_id), prefer_date=target_date)
    if not isinstance(row, dict):
        return VerificationResult(
            completed=False,
            progress=0.0,
            evidence={"verifier": QuestVerifierKind.LXP_ATTENDANCE, "snapshot_date": target_date.isoformat()},
            message="Нет данных посещаемости",
        )

    percent = _attendance_percent(row)
    if percent is None:
        return VerificationResult(
            completed=False,
            progress=0.0,
            evidence={"verifier": QuestVerifierKind.LXP_ATTENDANCE, "percent": None},
            message="Посещаемость по дисциплинам не пришла в снимке",
        )

    return VerificationResult(
        completed=percent >= min_percent,
        progress=min(1.0, percent / min_percent) if min_percent else 0.0,
        evidence={
            "verifier": QuestVerifierKind.LXP_ATTENDANCE,
            "percent": percent,
            "min_percent": min_percent,
        },
        message=f"Посещаемость {percent}% при пороге {min_percent}%",
    )


def _count_closed_ct(row: dict | None) -> int:
    if not isinstance(row, dict):
        return 0
    count = 0
    for _disc_id, disc in row.items():
        if not isinstance(disc, dict):
            continue
        topics = disc.get("topics") or []
        if isinstance(topics, dict):
            topics = topics.values()
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            if is_topic_closed(topic.get("status") or topic.get("state")):
                count += 1
    return count


def verify_lxp_ct_closed(user: User, params: dict, target_date: date) -> VerificationResult:
    if not user.lxp_user_id:
        return VerificationResult(
            completed=False,
            progress=0.0,
            evidence={"verifier": QuestVerifierKind.LXP_CT_CLOSED, "error": "no_lxp_user_id"},
            message="Нет привязки LXP",
        )
    min_closed = int(params.get("min_closed", 1))
    row = get_student_ct(str(user.lxp_user_id), prefer_date=target_date)
    closed = _count_closed_ct(row)
    progress = min(1.0, closed / min_closed) if min_closed else 0.0
    completed = closed >= min_closed
    return VerificationResult(
        completed=completed,
        progress=progress,
        evidence={"verifier": QuestVerifierKind.LXP_CT_CLOSED, "closed_count": closed, "min_closed": min_closed},
        message=f"Закрыто КТ: {closed}/{min_closed}",
    )


def _yougile_belongs_to_user(payload: dict, user: User) -> bool:
    candidates: list[str] = []
    for key in ("assignee", "executor", "email", "user_email", "username"):
        val = payload.get(key)
        if val:
            candidates.append(str(val).lower())
    nested = payload.get("user") or payload.get("assignee_user")
    if isinstance(nested, dict):
        for key in ("email", "username", "name"):
            val = nested.get(key)
            if val:
                candidates.append(str(val).lower())
    email = (user.email or "").lower()
    username = user.username.lower()
    return any(email in c or username in c or c == email or c == username for c in candidates)


def _yougile_is_completion(payload: dict) -> bool:
    for key in ("type", "event", "action", "status", "state"):
        val = str(payload.get(key) or "").lower()
        if any(token in val for token in ("done", "complete", "closed", "archived", "finished")):
            return True
    return False


def verify_yougile_tasks(user: User, params: dict, target_date: date) -> VerificationResult:
    days = int(params.get("days", 7))
    min_count = int(params.get("min_count", 3))
    since = timezone.make_aware(datetime.combine(target_date - timedelta(days=days - 1), time.min))
    matched = 0
    # У событий YouGile нет привязки к пользователю (вебхук приходит с чужой
    # стороны), поэтому фильтруем по времени и сопоставляем в Python.
    for ev in ExternalEvent.objects.filter(source="yougile", processed_at__gte=since).only("payload").iterator(
        chunk_size=500
    ):
        payload = ev.payload or {}
        if not _yougile_belongs_to_user(payload, user):
            continue
        if _yougile_is_completion(payload):
            matched += 1
    progress = min(1.0, matched / min_count) if min_count else 0.0
    return VerificationResult(
        completed=matched >= min_count,
        progress=progress,
        evidence={"verifier": QuestVerifierKind.YOUGILE_TASKS, "matched": matched, "min_count": min_count},
        message=f"Задач YouGile: {matched}/{min_count}",
    )


def verify_late_streak(user: User, params: dict, target_date: date) -> VerificationResult:
    min_days = int(params.get("min_days", 7))
    strike, _ = UserStrike.objects.get_or_create(user=user)
    current = strike.late_strike
    progress = min(1.0, current / min_days) if min_days else 0.0
    return VerificationResult(
        completed=current >= min_days,
        progress=progress,
        evidence={"verifier": QuestVerifierKind.LATE_STREAK, "late_strike": current, "min_days": min_days},
        message=f"Серия без опозданий: {current}/{min_days} дн.",
    )


VERIFIERS = {
    QuestVerifierKind.HIK_ON_TIME: verify_hik_on_time,
    QuestVerifierKind.HIK_NO_LATE: verify_hik_no_late,
    QuestVerifierKind.LXP_ATTENDANCE: verify_lxp_attendance,
    QuestVerifierKind.LXP_CT_CLOSED: verify_lxp_ct_closed,
    QuestVerifierKind.YOUGILE_TASKS: verify_yougile_tasks,
    QuestVerifierKind.LATE_STREAK: verify_late_streak,
}


def run_verifier(user: User, verifier: str, params: dict, target_date: date) -> VerificationResult:
    fn = VERIFIERS.get(verifier)
    if not fn:
        return VerificationResult(
            completed=False,
            progress=0.0,
            evidence={"error": "unknown_verifier", "verifier": verifier},
            message="Неизвестный тип проверки",
        )
    return fn(user, params or {}, target_date)
