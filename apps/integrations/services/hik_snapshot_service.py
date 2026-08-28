"""Импорт снимков Hik (ручной забор) → HikEvent → ExternalEvent."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, time
from pathlib import Path

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import Role
from apps.integrations.models import HikSnapshot
from apps.integrations.services.hik_attendance_processor import (
    process_unprocessed_hik_events,
    save_hik_row_as_event,
)

logger = logging.getLogger(__name__)
User = get_user_model()
SYNTHETIC_HIK_CARD_BASE = "HIK-DEMO"


def normalize_snapshot_payload(raw, target_date: date) -> dict:
    """Приводит JSON из файла/экспорта к единому формату."""
    if isinstance(raw, list):
        events = raw
        meta = {"source": "file", "format": "list"}
    elif isinstance(raw, dict):
        if isinstance(raw.get("events"), list):
            events = raw["events"]
            meta = dict(raw.get("meta") or {})
        elif isinstance(raw.get("data"), dict) and isinstance(raw["data"].get("list"), list):
            events = raw["data"]["list"]
            meta = {"source": "file", "format": "artemis_pages"}
        elif isinstance(raw.get("data"), list):
            events = raw["data"]
            meta = {"source": "file", "format": "data_list"}
        else:
            events = []
            meta = {"source": "file", "format": "unknown"}
    else:
        events = []
        meta = {"source": "file", "format": "invalid"}

    meta.setdefault("source", "manual")
    meta["events_count"] = len(events)
    meta["imported_at"] = timezone.now().isoformat()

    return {
        "date": target_date.isoformat(),
        "meta": meta,
        "events": events,
    }


def load_snapshot_from_file(path: str | Path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text)


def save_hik_snapshot(target_date: date, data: dict, *, force: bool = False) -> HikSnapshot:
    """Сохранить снимок за день, не ухудшая уже сохранённый.

    Снимок перезаписывался целиком: неудачная выгрузка (портал вернул пустой
    файл, сессия отвалилась, экспорт скачался обрезанным) стирала валидные
    данные за этот день, а созданные из них HikEvent оставались — состояние
    расходилось. Пустой результат поверх непустого больше не принимается.
    """
    normalized = normalize_snapshot_payload(data, target_date)
    new_events = len(normalized.get("events") or [])

    existing = HikSnapshot.objects.filter(date=target_date).first()
    if existing and not force:
        old_events = len((existing.data or {}).get("events") or [])
        if new_events == 0 and old_events > 0:
            logger.warning(
                "Hik snapshot %s: пустая выгрузка не записана поверх снимка с %s событиями",
                target_date,
                old_events,
            )
            return existing

    snap, _ = HikSnapshot.objects.update_or_create(date=target_date, defaults={"data": normalized})
    return snap


def build_synthetic_snapshot(
    target_date: date,
    *,
    assign_missing_cards: bool = False,
) -> dict:
    """Демо-снимок: у каждого агента проход «вовремя» утром."""
    events: list[dict] = []
    qs = User.objects.filter(role=Role.AGENT).order_by("id")
    for user in qs.iterator(chunk_size=200):
        code = (user.hik_card_code or "").strip()
        if not code and assign_missing_cards:
            code = f"{SYNTHETIC_HIK_CARD_BASE}-{user.pk}"
            user.hik_card_code = code
            user.save(update_fields=["hik_card_code"])
        if not code:
            continue
        event_time = timezone.make_aware(datetime.combine(target_date, time(8, 45)))
        events.append(
            {
                "eventId": f"synthetic-{target_date.isoformat()}-{user.pk}",
                "personCode": code,
                "eventTime": event_time.isoformat(),
                "eventType": "access",
                "doorName": "Demo Gate",
            }
        )
    return normalize_snapshot_payload(
        {"events": events, "meta": {"source": "synthetic", "assign_missing_cards": assign_missing_cards}},
        target_date,
    )


def import_snapshot_to_hik_events(snapshot: HikSnapshot) -> tuple[int, int, int]:
    """Импорт строк снимка в HikEvent. Возвращает (seen, inserted, skipped)."""
    events = get_events_from_snapshot(snapshot)
    seen = 0
    inserted = 0
    skipped = 0
    for row in events:
        if not isinstance(row, dict):
            skipped += 1
            continue
        seen += 1
        _, created = save_hik_row_as_event(row)
        if created:
            inserted += 1
    return seen, inserted, skipped


def get_events_from_snapshot(snapshot: HikSnapshot) -> list:
    data = snapshot.data or {}
    events = data.get("events")
    return events if isinstance(events, list) else []


def apply_hik_snapshot(
    target_date: date,
    *,
    skip_process: bool = False,
    process_limit: int = 50_000,
) -> dict:
    """
    Полный цикл: импорт HikEvent из снимка → ExternalEvent + штрафы.
    """
    snapshot = HikSnapshot.objects.filter(date=target_date).first()
    if not snapshot:
        return {"error": "no_snapshot", "date": target_date.isoformat()}

    imp_seen, imp_new, imp_skip = import_snapshot_to_hik_events(snapshot)
    result = {
        "date": target_date.isoformat(),
        "import_seen": imp_seen,
        "import_inserted": imp_new,
        "import_skipped": imp_skip,
    }

    if skip_process:
        result["process_skipped"] = True
        return result

    proc_seen, ext_created, skipped_no_user = process_unprocessed_hik_events(limit=process_limit)
    result.update(
        {
            "process_seen": proc_seen,
            "external_created": ext_created,
            "skipped_no_user": skipped_no_user,
        }
    )
    logger.info("apply_hik_snapshot %s", result)
    return result


def export_snapshot_template() -> dict:
    """Пример формата для ручной выгрузки."""
    today = timezone.localdate()
    return {
        "date": today.isoformat(),
        "meta": {"source": "manual_export", "note": "Замените personCode на hik_card_code пользователя"},
        "events": [
            {
                "eventId": "example-001",
                "personCode": "CARD-12345",
                "eventTime": timezone.make_aware(datetime.combine(today, time(8, 55))).isoformat(),
                "eventType": "access",
                "doorName": "Main entrance",
            }
        ],
    }
