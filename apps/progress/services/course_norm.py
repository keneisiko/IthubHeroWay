"""Нормировка стоимости контрольной точки по курсу.

Годовой бюджет за КТ один для всех, а число тем у курсов разное. Цена одной
темы = бюджет / ожидаемое число тем курса, поэтому и первокурсник с 60 темами,
и третьекурсник с 30 могут набрать за год примерно одинаковый максимум.

Ожидаемое число тем не задаётся руками: берётся наблюдаемый по курсу максимум
объёма тем на студента. Он только растёт по мере появления новых дисциплин,
поэтому цена темы к концу года снижается, а не скачет туда-сюда.
"""

from __future__ import annotations

from django.conf import settings

from apps.progress.models import CourseTopicNorm

NO_COURSE = 0


def _cfg() -> dict:
    return getattr(settings, "RATING_YEAR", {})


def observe_course_volume(course: int | None, topics_total: int) -> None:
    """Запомнить объём тем, если он больше ранее наблюдавшегося по курсу."""
    if topics_total <= 0:
        return
    key = int(course or NO_COURSE)
    row, created = CourseTopicNorm.objects.get_or_create(
        course=key, defaults={"expected_topics": topics_total}
    )
    if not created and topics_total > row.expected_topics:
        row.expected_topics = topics_total
        row.save(update_fields=["expected_topics", "updated_at"])


def points_per_topic(course: int | None) -> int:
    """Сколько рейтинга даёт одна закрытая тема студенту этого курса."""
    cfg = _cfg()
    budget = int(cfg.get("CT_YEAR_BUDGET", 400))
    low = int(cfg.get("CT_POINTS_MIN", 4))
    high = int(cfg.get("CT_POINTS_MAX", 40))
    fallback = int(cfg.get("CT_EXPECTED_TOPICS_FALLBACK", 40))

    row = CourseTopicNorm.objects.filter(course=int(course or NO_COURSE)).first()
    expected = row.expected_topics if row and row.expected_topics > 0 else fallback
    return max(low, min(high, round(budget / expected)))


def expected_topics(course: int | None) -> int:
    row = CourseTopicNorm.objects.filter(course=int(course or NO_COURSE)).first()
    if row and row.expected_topics > 0:
        return row.expected_topics
    return int(_cfg().get("CT_EXPECTED_TOPICS_FALLBACK", 40))
