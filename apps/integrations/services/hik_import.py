"""Импорт проходов из портала с записью в журнал `HikImportRun`.

Одна точка, через которую идут и Celery-задача, и management-команда: иначе
журнал заполняется только в одном из путей, и по нему нельзя судить
о состоянии интеграции.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time

from django.utils import timezone

from apps.integrations.models import HikImportMode, HikImportRun, HikImportStatus
from apps.integrations.services.hik_attendance_processor import (
    process_unprocessed_hik_events,
    save_hik_row_as_event,
)
from apps.integrations.services.hik_web_fetch import fetch_rows_for_range

logger = logging.getLogger(__name__)


@dataclass
class ImportOutcome:
    run: HikImportRun
    rows: list[dict]

    @property
    def ok(self) -> bool:
        return self.run.status != HikImportStatus.ERROR


def range_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_from, dt_time.min), tz)
    end = timezone.make_aware(datetime.combine(date_to, dt_time.max), tz)
    return start, end


def import_from_portal(
    date_from: date,
    date_to: date,
    *,
    process: bool = True,
    mode: str = HikImportMode.WEB_API,
) -> ImportOutcome:
    """Забрать записи за период, сохранить и разобрать очередь.

    Любой исход фиксируется в `HikImportRun`: успех, пустой период и ошибка
    различимы, а не сливаются в одинаковую строку с нулями.
    """
    started = time.monotonic()
    start, end = range_bounds(date_from, date_to)

    run = HikImportRun(
        mode=mode,
        status=HikImportStatus.ERROR,
        date_from=date_from,
        date_to=date_to,
    )

    try:
        fetched = fetch_rows_for_range(start, end)
    except Exception as exc:
        run.error = f"{type(exc).__name__}: {exc}"[:2000]
        run.duration_ms = int((time.monotonic() - started) * 1000)
        run.save()
        logger.warning("hik_import: ошибка выгрузки %s..%s: %s", date_from, date_to, exc)
        raise

    rows = fetched.rows
    run.relogin_used = fetched.relogin_used
    run.records_fetched = len(rows)

    created = 0
    for row in rows:
        _, was_created = save_hik_row_as_event(row)
        if was_created:
            created += 1
    run.events_created = created

    if process and rows:
        _, external_created, unmatched = process_unprocessed_hik_events(limit=50_000)
        run.external_created = external_created
        run.users_unmatched = unmatched

    run.status = HikImportStatus.SUCCESS if rows else HikImportStatus.EMPTY
    run.duration_ms = int((time.monotonic() - started) * 1000)
    run.save()

    logger.info(
        "hik_import %s..%s: получено=%s новых=%s external=%s без_привязки=%s",
        date_from,
        date_to,
        run.records_fetched,
        run.events_created,
        run.external_created,
        run.users_unmatched,
    )
    return ImportOutcome(run=run, rows=rows)


def last_successful_run() -> HikImportRun | None:
    return (
        HikImportRun.objects.filter(status=HikImportStatus.SUCCESS)
        .order_by("-started_at")
        .first()
    )
