"""Опоры «Фокус», «Связь» и «Отдача» — из того, что студент делает на платформе.

Раньше все три считались одной формулой «рейтинг ÷ 100»: у 573 из 574
студентов они совпадали, при списаниях уходили в минус, а при рейтинге выше
2000 вылезали за шкалу 20. Пятиугольник по сути был треугольником.

Окно — последние 28 дней, но не раньше начала сезона: сезон по Положению
начинается с нуля, и прошлогодняя активность в нём не считается.
Шкала у всех опор 0–20.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Q

from apps.integrations.models import ExternalEvent
from apps.progress.services.polozhenie_period import season_start_date
from apps.quests.models import SelfReportProof, SelfReportProofStatus, UserQuestProgress
from apps.social.models import Duel, DuelStatus, Mentorship, Respect

PILLAR_FOCUS = "discipline"
PILLAR_TEAMWORK = "teamwork"
PILLAR_INITIATIVE = "initiative"

WINDOW_DAYS = 28
SCALE = 20.0

# Сколько «очков» за окно дают полную шкалу. Активный студент: квест в день
# или около того — Отдача 20; пара респектов в неделю плюс шефство — Связь 20.
INITIATIVE_FULL = 20
TEAMWORK_FULL = 20

# Веса внутри опор
WEIGHT_SELF_REPORT = 2  # одобренный самоотчёт весит как два квеста: его проверяет человек
WEIGHT_RESPECT_RECEIVED = 2
WEIGHT_RESPECT_GIVEN = 1
WEIGHT_MENTORSHIP = 6  # действующее шефство — наставник или подопечный
WEIGHT_DUEL = 2


def window_start(today: date) -> date:
    return max(today - timedelta(days=WINDOW_DAYS - 1), season_start_date())


def _scaled(points: float, full: float) -> float:
    return round(max(0.0, min(SCALE, points / full * SCALE)), 1)


def focus(user_id: int, start: date, end: date) -> float | None:
    """Пунктуальность по Hik: доля дней присутствия без опоздания.

    Нет ни одного прохода за окно — не знаем, а не «ноль»: опора не
    пересчитывается, чтобы сбой выгрузки не обнулял студенту Фокус.
    """
    rows = ExternalEvent.objects.filter(
        source="hik", user_id=user_id, event_date__range=(start, end)
    ).values_list("event_date", "event_type")
    present: set[date] = set()
    late: set[date] = set()
    for day, event_type in rows:
        present.add(day)
        if event_type == "late":
            late.add(day)
    if not present:
        return None
    return round((len(present) - len(late)) / len(present) * SCALE, 1)


def initiative(user_id: int, start: date, end: date) -> float:
    """Выполненные квесты и одобренные самоотчёты."""
    quests = UserQuestProgress.objects.filter(
        user_id=user_id, is_completed=True, completed_at__date__range=(start, end)
    ).count()
    reports = SelfReportProof.objects.filter(
        user_id=user_id,
        status=SelfReportProofStatus.APPROVED,
        reviewed_at__date__range=(start, end),
    ).count()
    return _scaled(quests + WEIGHT_SELF_REPORT * reports, INITIATIVE_FULL)


def teamwork(user_id: int, start: date, end: date) -> float:
    """Респекты, шефство и дуэли — всё, где участвует другой студент."""
    received = Respect.objects.filter(to_user_id=user_id, created_at__date__range=(start, end)).count()
    given = Respect.objects.filter(from_user_id=user_id, created_at__date__range=(start, end)).count()
    # Шефство считается, если шло хотя бы часть окна.
    mentoring = Mentorship.objects.filter(
        Q(mentor_id=user_id) | Q(mentee_id=user_id),
        Q(ended_at__isnull=True) | Q(ended_at__date__gte=start),
    ).exists()
    duels = Duel.objects.filter(
        Q(challenger_id=user_id) | Q(opponent_id=user_id),
        status=DuelStatus.FINISHED,
        resolved_at__date__range=(start, end),
    ).count()
    points = (
        WEIGHT_RESPECT_RECEIVED * received
        + WEIGHT_RESPECT_GIVEN * given
        + (WEIGHT_MENTORSHIP if mentoring else 0)
        + WEIGHT_DUEL * duels
    )
    return _scaled(points, TEAMWORK_FULL)


def activity_pillars(user_id: int, today: date) -> dict[str, float | None]:
    start = window_start(today)
    return {
        PILLAR_FOCUS: focus(user_id, start, today),
        PILLAR_TEAMWORK: teamwork(user_id, start, today),
        PILLAR_INITIATIVE: initiative(user_id, start, today),
    }
