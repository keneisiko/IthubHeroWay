"""Экземпляры квестов на период.

Награда за квест уникальна по паре «пользователь + квест», а шаблоны создавали
одну строку `Quest` на код. Из-за этого «ежедневный» квест приносил монеты
ровно один раз за всё время: на второй день `QuestRewardTransaction` уже
существовал, а прогресс навсегда оставался выполненным.

Теперь на каждый день (и на каждую неделю) заводится отдельный экземпляр
квеста с ключом периода в коде: `daily-hik-on-time:2026-08-27`.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.utils import timezone

from apps.quests.models import Quest, QuestTemplate, QuestType

PERIODIC_TYPES = (QuestType.DAILY, QuestType.WEEKLY)


def period_key_for(quest_type: str, day: date) -> str:
    """Ключ периода: дата для ежедневных, ISO-неделя для еженедельных."""
    if quest_type == QuestType.DAILY:
        return day.isoformat()
    if quest_type == QuestType.WEEKLY:
        iso_year, iso_week, _ = day.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return ""


def period_bounds(quest_type: str, day: date) -> tuple[datetime, datetime]:
    """Начало и конец периода в часовом поясе проекта."""
    if quest_type == QuestType.WEEKLY:
        start_day = day - timedelta(days=day.weekday())
        end_day = start_day + timedelta(days=6)
    else:
        start_day = end_day = day
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(start_day, time.min), tz)
    end = timezone.make_aware(datetime.combine(end_day, time.max), tz)
    return start, end


def ensure_period_quests(day: date | None = None) -> dict:
    """Создать экземпляры периодических квестов для даты.

    Идемпотентно: повторный вызов за тот же день ничего не создаёт.
    """
    day = day or timezone.localdate()
    created = 0
    existing = 0

    templates = QuestTemplate.objects.filter(is_active=True, quest_type__in=PERIODIC_TYPES)
    for template in templates:
        key = period_key_for(template.quest_type, day)
        start_at, end_at = period_bounds(template.quest_type, day)
        _, was_created = Quest.objects.get_or_create(
            code=f"{template.code}:{key}",
            defaults={
                "title": template.title,
                "description": template.description,
                "quest_type": template.quest_type,
                "reward_coins": template.reward_coins,
                "reward_rating_delta": template.reward_rating_delta,
                "conditions": template.build_conditions(),
                "is_active": True,
                "period_key": key,
                "start_at": start_at,
                "end_at": end_at,
            },
        )
        if was_created:
            created += 1
        else:
            existing += 1

    return {"date": day.isoformat(), "created": created, "existing": existing}


def quests_for_date(day: date, quest_types: list[str] | None = None):
    """Квесты, действующие на эту дату.

    Периодические берутся строго своего периода, непериодические (событийные,
    длинные, самоотчёты) — как раньше, по окну start_at/end_at.
    """
    from django.db.models import Q

    types = list(quest_types) if quest_types else None
    qs = Quest.objects.filter(is_active=True)
    if types:
        qs = qs.filter(quest_type__in=types)

    period_filter = Q(period_key="")
    for quest_type in PERIODIC_TYPES:
        if types and quest_type not in types:
            continue
        period_filter |= Q(quest_type=quest_type, period_key=period_key_for(quest_type, day))

    moment = timezone.make_aware(
        datetime.combine(day, time(12, 0)), timezone.get_current_timezone()
    )
    return (
        qs.filter(period_filter)
        .filter(Q(start_at__isnull=True) | Q(start_at__lte=moment))
        .filter(Q(end_at__isnull=True) | Q(end_at__gte=moment))
        .order_by("id")
    )
