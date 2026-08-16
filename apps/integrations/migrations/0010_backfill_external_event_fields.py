"""Перенести user / дату / тип события из payload в отдельные колонки.

Раньше эти значения жили только внутри JSON, и выборка «события пользователя
за день» делалась перебором всей таблицы в Python. Колонки с индексами
позволяют фильтровать в БД.
"""

from datetime import datetime

from django.db import migrations
from django.utils import timezone

BATCH = 1000


def _parse_event_date(raw):
    if not raw or not isinstance(raw, str):
        return None
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment, timezone.get_current_timezone())
    # Дата считается в часовом поясе проекта: расписание и опоздания живут в нём.
    return timezone.localtime(moment).date()


def backfill(apps, schema_editor):
    ExternalEvent = apps.get_model("integrations", "ExternalEvent")

    updated = 0
    batch = []
    queryset = ExternalEvent.objects.filter(user__isnull=True, event_date__isnull=True)

    for event in queryset.iterator(chunk_size=BATCH):
        payload = event.payload or {}
        if not isinstance(payload, dict):
            continue

        user_id = payload.get("user_id")
        event.user_id = user_id if isinstance(user_id, int) else None
        event.event_date = _parse_event_date(payload.get("event_time"))
        event.event_type = str(payload.get("event_type") or "")[:32]

        if event.user_id is None and event.event_date is None and not event.event_type:
            continue

        batch.append(event)
        if len(batch) >= BATCH:
            ExternalEvent.objects.bulk_update(batch, ["user_id", "event_date", "event_type"])
            updated += len(batch)
            batch = []

    if batch:
        ExternalEvent.objects.bulk_update(batch, ["user_id", "event_date", "event_type"])
        updated += len(batch)

    if updated:
        print(f"  заполнено полей у событий: {updated}")


def noop(apps, schema_editor):
    """Данные остаются в payload, откатывать нечего."""


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0009_externalevent_event_date_externalevent_event_type_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
