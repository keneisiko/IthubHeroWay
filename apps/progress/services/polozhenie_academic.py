"""Учебные начисления по разделу 3 Положения.

    Б = 17 × К / 100 + 13 × П / 100

где К — средний процент актуальных КТ текущего семестра, П — процент
посещаемости недели. Студент получает Б рейтинговых баллов и Б монет.

Это уровневая модель: каждая неделя оплачивает *поддерживаемый* уровень,
а не отдельное событие. Тем она и отличается от прежней событийной модели
(`lxp_rating_from_snapshot`), где балл давала сама сдача КТ. Пункт 3.4
говорит об этом прямо, поэтому событийные начисления из снимка отключены —
см. `LXP_EVENT_RATING_ENABLED`.

Две части считаются и начисляются независимо. Так требует п. 3.6: если нет
данных по одной из них, её расчёт откладывается и восстанавливается позже,
а вторая часть выплачивается сразу. Отсутствие данных не является нарушением
и нулём не считается.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.conf import settings

from apps.accounts.models import Role, User
from apps.integrations.models import LXPSnapshot
from apps.integrations.services.account_gate import agents_for_scoring
from apps.integrations.services.lxp_snapshot_format import unwrap_category
from apps.operations.services.platform_settings import platform_setting
from apps.progress.models import LessonAttendance, LessonAttendanceStatus, RatingChangeSource
from apps.progress.services.polozhenie_ledger import grant
from apps.progress.services.polozhenie_period import (
    is_payable_week,
    payable_window_start,
    period_key,
    quantize_money,
    week_end,
    week_start,
)

logger = logging.getLogger(__name__)

# Отметки, означающие присутствие. п. 3.2: отсутствие отметки «Н» в
# заполненном журнале проведённой пары считается присутствием, поэтому
# очное и онлайн-присутствие равноценны.
PRESENT_STATUSES = (LessonAttendanceStatus.PRESENT, LessonAttendanceStatus.ONLINE)


@dataclass(frozen=True)
class WeeklyComponents:
    """Составляющие недельного начисления одного студента."""

    ct_percent: Decimal | None
    attendance_percent: Decimal | None
    lessons_total: int = 0
    lessons_attended: int = 0
    topics_actual: int = 0
    topics_passed: int = 0


def is_pending_topic(status) -> bool:
    """Тема сдана и ждёт решения преподавателя — в расчёт не входит.

    По живым данным это треть всех тем, с которыми студент что-то делал:
    3153 из 4878. Считать их несданными значило бы отнимать у студента
    баллы за то, что преподаватель ещё не проверил работу, — тот же принцип,
    что в п. 3.6: решения нет, значит расчёт по этой теме отложен.
    """
    text = ("" if status is None else str(status)).strip().upper()
    if not text:
        return False
    markers = getattr(settings, "POLOZHENIE_PENDING_TOPIC_MARKERS", ())
    return any(marker in text for marker in markers)


def is_future_topic(status) -> bool:
    """Будущая КТ: в расчёт успеваемости не входит (п. 3.1)."""
    text = ("" if status is None else str(status)).strip().upper()
    if not text:
        # Пустой статус — это не «будущая», а «неизвестно». Считать такую КТ
        # актуальной и несданной означало бы штрафовать за пробел в выгрузке.
        return True
    markers = getattr(settings, "POLOZHENIE_FUTURE_TOPIC_MARKERS", ())
    return any(marker in text for marker in markers)


def topic_breakdown(control_points_for_user: dict) -> dict[str, int]:
    """Сколько у студента тем каждого вида — для диагностики.

    По одному проценту не видно, почему он такой: 100% получается и у того,
    кто сдал двадцать тем из двадцати, и у того, кто взялся за одну.
    Разбивка показывает знаменатель, на котором стоит начисление.
    """
    from apps.progress.services.ct_status import is_topic_closed

    counts = {"passed": 0, "open": 0, "pending": 0, "future": 0, "disciplines": 0}
    if not isinstance(control_points_for_user, dict):
        return counts

    for discipline in control_points_for_user.values():
        if not isinstance(discipline, dict):
            continue
        counts["disciplines"] += 1
        topics = discipline.get("topics") or []
        if isinstance(topics, dict):
            topics = list(topics.values())
        if not isinstance(topics, list):
            continue
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            status = topic.get("status") or topic.get("state")
            if is_future_topic(status):
                counts["future"] += 1
            elif is_pending_topic(status):
                counts["pending"] += 1
            elif is_topic_closed(status):
                counts["passed"] += 1
            else:
                counts["open"] += 1
    return counts


def ct_scope() -> str:
    return str(platform_setting("ct_scope"))


def ct_percent_from_snapshot(control_points_for_user: dict) -> tuple[Decimal | None, int, int]:
    """Средний процент актуальных КТ студента.

    Сознательно: это процент ТЕКУЩЕГО состояния тем, а не прирост за период, поэтому
    в неделю запуска начислений он учтёт и темы, сданные раньше.

    Возвращает (процент, сколько актуальных, сколько сданных). Процент равен
    `None`, когда считать не из чего: п. 3.6 — начисление компонента не
    производится до появления основания, а откладывается.

    Что считать актуальным, задаёт `POLOZHENIE_CT_SCOPE`. Пока правило не
    выбрано, компонент откладывается целиком: по проверенному на живых данных
    правилу «решённые» 15 студентов из 17 получали 100% и полные 17 баллов.
    """
    from apps.progress.services.ct_status import is_topic_closed

    scope = ct_scope()
    if scope == "deferred":
        return None, 0, 0

    if not isinstance(control_points_for_user, dict):
        return None, 0, 0

    count_pending_as_actual = scope == "decided_with_pending"

    actual = 0
    passed = 0
    for discipline in control_points_for_user.values():
        if not isinstance(discipline, dict):
            continue
        topics = discipline.get("topics") or []
        if isinstance(topics, dict):
            topics = list(topics.values())
        if not isinstance(topics, list):
            continue
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            status = topic.get("status") or topic.get("state")
            if is_future_topic(status):
                continue
            if is_pending_topic(status) and not count_pending_as_actual:
                continue
            actual += 1
            if is_topic_closed(status):
                passed += 1

    min_actual = int(platform_setting("ct_min_actual"))
    if actual < max(1, min_actual):
        # Слишком мало тем, чтобы процент что-то значил: одна несданная из
        # одной — это ноль, одна сданная — сотня. Откладываем до данных.
        return None, actual, passed

    # п. 3.1: несданная актуальная КТ учитывается как 0%. Значит средний
    # процент — это доля сданных среди актуальных.
    return quantize_money(Decimal(passed) * 100 / Decimal(actual)), actual, passed


def attendance_percent_for_week(user: User, start: date, end: date) -> tuple[Decimal | None, int, int]:
    """Процент посещаемости недели по отметкам занятий (п. 3.2).

    Возвращает (процент, всего пар, посещено). Процент равен `None`, когда
    пар на неделе не было: п. 3.6 — неделя без занятий не считается нулевой
    посещаемостью.
    """
    marks = list(
        LessonAttendance.objects.filter(
            user=user, lesson_date__gte=start, lesson_date__lte=end
        ).values_list("status", flat=True)
    )
    total = len(marks)
    if total == 0:
        return None, 0, 0
    attended = sum(1 for status in marks if status in PRESENT_STATUSES)
    return quantize_money(Decimal(attended) * 100 / Decimal(total)), total, attended


def snapshot_ct_data(start: date, end: date) -> dict:
    """Данные КТ из последнего снимка на конец недели.

    Снимок берётся не старше конца недели: успеваемость оплачивается по
    состоянию на расчётную неделю, а не по сегодняшнему.
    """
    snap = LXPSnapshot.objects.filter(date__lte=end).order_by("-date").first()
    if snap is None:
        return {}
    block = (snap.data or {}).get("control_points")
    if not isinstance(block, dict) or not block.get("ok"):
        return {}
    return unwrap_category(block)


def components_for_user(user: User, start: date, end: date, ct_data: dict) -> WeeklyComponents:
    lxp_uid = (user.lxp_user_id or "").strip()
    ct_percent, actual, passed = (None, 0, 0)
    if lxp_uid:
        row = ct_data.get(lxp_uid)
        if isinstance(row, dict) and row:
            ct_percent, actual, passed = ct_percent_from_snapshot(row)

    att_percent, lessons, attended = attendance_percent_for_week(user, start, end)
    return WeeklyComponents(
        ct_percent=ct_percent,
        attendance_percent=att_percent,
        lessons_total=lessons,
        lessons_attended=attended,
        topics_actual=actual,
        topics_passed=passed,
    )


def _tariff(name: str, default: str) -> Decimal:
    return Decimal(str(getattr(settings, "POLOZHENIE_ACADEMIC", {}).get(name, Decimal(default))))


def accrue_week_for_user(user: User, day: date) -> dict:
    """Начислить студенту за учебную неделю, в которую попадает `day`."""
    start, end = week_start(day), week_end(day)
    key = period_key(start)
    ct_data = snapshot_ct_data(start, end)
    window = payable_window_start(day)
    return _accrue(user, start, end, key, components_for_user(user, window, end, ct_data))


def _accrue(user: User, start: date, end: date, key: str, parts: WeeklyComponents) -> dict:
    ct_max = _tariff("CT_WEEKLY_MAX", "17")
    att_max = _tariff("ATTENDANCE_WEEKLY_MAX", "13")

    granted_rating = Decimal("0")
    granted_coins = Decimal("0")
    deferred: list[str] = []

    if parts.ct_percent is None:
        deferred.append("ct")
    else:
        value = quantize_money(ct_max * parts.ct_percent / 100)
        res = grant(
            user,
            rating=value,
            coins=value,
            source=RatingChangeSource.ACADEMIC,
            source_id=f"week:{key}:ct",
            reason=(
                f"Успеваемость за {key}: КТ {parts.ct_percent}% "
                f"({parts.topics_passed} из {parts.topics_actual} актуальных)"
            ),
            period=key,
        )
        granted_rating += res.rating_delta
        granted_coins += res.coins_delta

    if parts.attendance_percent is None:
        deferred.append("attendance")
    else:
        value = quantize_money(att_max * parts.attendance_percent / 100)
        res = grant(
            user,
            rating=value,
            coins=value,
            source=RatingChangeSource.ACADEMIC,
            source_id=f"week:{key}:attendance",
            reason=(
                f"Посещаемость за {key}: {parts.attendance_percent}% "
                f"({parts.lessons_attended} из {parts.lessons_total} пар)"
            ),
            period=key,
        )
        granted_rating += res.rating_delta
        granted_coins += res.coins_delta

    return {
        "period": key,
        "week_start": start,
        "week_end": end,
        "rating": granted_rating,
        "coins": granted_coins,
        "deferred": deferred,
        "ct_percent": parts.ct_percent,
        "attendance_percent": parts.attendance_percent,
    }


@dataclass(frozen=True)
class WeeklyAccrualResult:
    period: str
    week_start: date
    week_end: date
    users_considered: int
    users_paid: int
    rating_total: Decimal
    coins_total: Decimal
    deferred_ct: int
    deferred_attendance: int
    notes: str = ""


def run_weekly_accrual(day: date | None = None) -> WeeklyAccrualResult:
    """Начисления за учебную неделю всем студентам (раздел 3)."""
    from django.utils import timezone

    day = day or timezone.localdate()
    start, end = week_start(day), week_end(day)
    key = period_key(start)

    if not is_payable_week(start):
        # п. 2.2: за период до общей даты запуска начисления не производятся.
        return WeeklyAccrualResult(
            period=key,
            week_start=start,
            week_end=end,
            users_considered=0,
            users_paid=0,
            rating_total=Decimal("0"),
            coins_total=Decimal("0"),
            deferred_ct=0,
            deferred_attendance=0,
            notes="before_season_start",
        )

    ct_data = snapshot_ct_data(start, end)
    # В неделе запуска учитываются только дни со дня включения.
    window = payable_window_start(day)
    considered = paid = deferred_ct = deferred_att = 0
    rating_total = Decimal("0")
    coins_total = Decimal("0")

    # Только агенты: без фильтра по роли сюда попадали бы кураторы, тьюторы
    # и администраторы — у них нет ни КТ, ни пар, но в отчёте они числились
    # бы «учтёнными», а запись в журнале появилась бы при любой отметке.
    audience = agents_for_scoring(User.objects.filter(role=Role.AGENT))
    for user in audience.select_related("squad").iterator(chunk_size=200):
        considered += 1
        parts = components_for_user(user, window, end, ct_data)
        outcome = _accrue(user, start, end, key, parts)
        if outcome["rating"] or outcome["coins"]:
            paid += 1
        rating_total += outcome["rating"]
        coins_total += outcome["coins"]
        if "ct" in outcome["deferred"]:
            deferred_ct += 1
        if "attendance" in outcome["deferred"]:
            deferred_att += 1

    logger.info(
        "polozhenie_weekly period=%s considered=%s paid=%s rating=%s coins=%s",
        key,
        considered,
        paid,
        rating_total,
        coins_total,
    )
    return WeeklyAccrualResult(
        period=key,
        week_start=start,
        week_end=end,
        users_considered=considered,
        users_paid=paid,
        rating_total=rating_total,
        coins_total=coins_total,
        deferred_ct=deferred_ct,
        deferred_attendance=deferred_att,
        notes=f"snapshot_rows={len(ct_data)}",
    )
