"""Import browser XLSX export into HikSnapshot pipeline."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from apps.integrations.models import HikSnapshot
from apps.integrations.services.hik_snapshot_service import (
    apply_hik_snapshot,
    normalize_snapshot_payload,
    save_hik_snapshot,
)
from apps.integrations.services.hik_xlsx_parser import snapshot_payload_from_export


def import_hik_export_file(
    path: str | Path,
    target_date: date,
    *,
    skip_process: bool = False,
) -> dict:
    payload = snapshot_payload_from_export(path, target_date)
    save_hik_snapshot(target_date, payload)
    # `skip_process` означает «не создавать ExternalEvent и не начислять
    # штрафы», но HikEvent создать нужно — иначе события теряются до ручного
    # повтора. Раньше эта ветка возвращалась раньше времени, и поведение
    # расходилось с pull_hik_attendance и с собственной справкой команды.
    return apply_hik_snapshot(target_date, skip_process=skip_process)


def save_export_copy(path: str | Path, target_date: date) -> HikSnapshot:
    payload = snapshot_payload_from_export(path, target_date)
    return save_hik_snapshot(target_date, normalize_snapshot_payload(payload, target_date))
