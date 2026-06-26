"""Parse Hik Connect XLSX/CSV exports into event rows for HikEvent import."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from datetime import date, datetime
from pathlib import Path

from django.utils import timezone
from django.utils.dateparse import parse_datetime

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover
    load_workbook = None  # type: ignore

CODE_HEADERS = (
    "personcode",
    "personno",
    "employeeno",
    "employeenumber",
    "cardno",
    "cardnumber",
    "personid",
    "id",
    "номеркарты",
    "номеркартыaccess",
    "табельныйномер",
    "номерсотрудника",
    "код",
)
TIME_HEADERS = (
    "time",
    "datetime",
    "date",
    "eventtime",
    "happentime",
    "checktime",
    "attendancetime",
    "время",
    "дата",
    "датаивремя",
    "времяпрохода",
    "времясобытия",
)
DOOR_HEADERS = (
    "door",
    "doorname",
    "device",
    "devicename",
    "accesspoint",
    "checkpoint",
    "location",
    "точкадоступа",
    "устройство",
    "турникет",
    "дверь",
)
TYPE_HEADERS = (
    "eventtype",
    "type",
    "eventname",
    "status",
    "attendancestatus",
    "тип",
    "типсобытия",
    "статус",
)
NAME_HEADERS = ("personname", "name", "employeename", "фио", "имя", "сотрудник")


def _norm_header(value: str) -> str:
    return re.sub(r"[\s_\-./\\()]+", "", (value or "").strip().lower())


def _pick_column(headers: list[str], candidates: tuple[str, ...]) -> int | None:
    normalized = [_norm_header(h) for h in headers]
    for idx, header in enumerate(normalized):
        if not header:
            continue
        for cand in candidates:
            if cand in header or header in cand:
                return idx
    return None


def _cell_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            return timezone.make_aware(value).isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).date().isoformat()
    return str(value).strip()


def _parse_time_value(raw: str, fallback_date: date | None = None) -> str:
    text = (raw or "").strip()
    if not text:
        if fallback_date:
            return timezone.make_aware(datetime.combine(fallback_date, datetime.min.time())).isoformat()
        return timezone.now().isoformat()
    dt = parse_datetime(text.replace("Z", "+00:00"))
    if dt:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt.isoformat()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(text, fmt)
            return timezone.make_aware(dt, timezone.get_current_timezone()).isoformat()
        except ValueError:
            continue
    if fallback_date:
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                t = datetime.strptime(text, fmt).time()
                dt = datetime.combine(fallback_date, t)
                return timezone.make_aware(dt, timezone.get_current_timezone()).isoformat()
            except ValueError:
                continue
    return text


def _rows_from_xlsx(path: Path) -> list[list[str]]:
    if load_workbook is None:
        raise RuntimeError("openpyxl is not installed")
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows: list[list[str]] = []
    for row in ws.iter_rows(values_only=True):
        rows.append([_cell_str(c) for c in row])
    wb.close()
    return rows


def _rows_from_csv(path: Path) -> list[list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    return [[cell.strip() for cell in row] for row in reader]


def _rows_from_zip(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            lower = name.lower()
            if lower.endswith(".xlsx"):
                data = zf.read(name)
                tmp = path.with_suffix(".inner.xlsx")
                tmp.write_bytes(data)
                try:
                    return _rows_from_xlsx(tmp)
                finally:
                    tmp.unlink(missing_ok=True)
            if lower.endswith(".csv"):
                text = zf.read(name).decode("utf-8-sig", errors="replace")
                reader = csv.reader(io.StringIO(text))
                return [[cell.strip() for cell in row] for row in reader]
    raise ValueError(f"No xlsx/csv found inside zip: {path}")


def load_tabular_rows(path: str | Path) -> list[list[str]]:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".zip":
        return _rows_from_zip(p)
    if suffix in {".xlsx", ".xlsm"}:
        return _rows_from_xlsx(p)
    if suffix == ".csv":
        return _rows_from_csv(p)
    raise ValueError(f"Unsupported export format: {suffix}")


def _find_header_row(rows: list[list[str]]) -> int:
    best_idx = 0
    best_score = -1
    for idx, row in enumerate(rows[:20]):
        score = 0
        joined = " ".join(_norm_header(c) for c in row if c)
        for group in (CODE_HEADERS, TIME_HEADERS, DOOR_HEADERS, TYPE_HEADERS, NAME_HEADERS):
            if any(token in joined for token in group):
                score += 1
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx


def parse_hik_export_rows(
    path: str | Path,
    *,
    fallback_date: date | None = None,
) -> list[dict]:
    """
    Convert XLSX/CSV/ZIP export to dict rows compatible with save_hik_row_as_event().
    """
    rows = load_tabular_rows(path)
    non_empty = [r for r in rows if any(cell.strip() for cell in r)]
    if not non_empty:
        return []

    header_idx = _find_header_row(non_empty)
    headers = non_empty[header_idx]
    data_rows = non_empty[header_idx + 1 :]

    code_col = _pick_column(headers, CODE_HEADERS)
    time_col = _pick_column(headers, TIME_HEADERS)
    door_col = _pick_column(headers, DOOR_HEADERS)
    type_col = _pick_column(headers, TYPE_HEADERS)
    name_col = _pick_column(headers, NAME_HEADERS)

    events: list[dict] = []
    for row_idx, row in enumerate(data_rows, start=1):
        if not any(cell.strip() for cell in row):
            continue
        code = row[code_col].strip() if code_col is not None and code_col < len(row) else ""
        if not code and name_col is not None and name_col < len(row):
            code = row[name_col].strip()
        if not code:
            continue

        time_raw = row[time_col].strip() if time_col is not None and time_col < len(row) else ""
        event_time = _parse_time_value(time_raw, fallback_date=fallback_date)
        door = row[door_col].strip() if door_col is not None and door_col < len(row) else ""
        event_type = row[type_col].strip() if type_col is not None and type_col < len(row) else "access"
        person_name = row[name_col].strip() if name_col is not None and name_col < len(row) else ""

        digest = hashlib.sha1(f"{code}|{event_time}|{door}|{row_idx}".encode()).hexdigest()[:16]
        event_id = f"xlsx-{digest}"
        event = {
            "eventId": event_id,
            "personCode": code,
            "eventTime": event_time,
            "eventType": event_type or "access",
            "doorName": door,
        }
        if person_name:
            event["personName"] = person_name
        events.append(event)
    return events


def snapshot_payload_from_export(path: str | Path, target_date: date) -> dict:
    events = parse_hik_export_rows(path, fallback_date=target_date)
    return {
        "date": target_date.isoformat(),
        "meta": {
            "source": "browser_xlsx",
            "file": Path(path).name,
            "events_count": len(events),
            "imported_at": timezone.now().isoformat(),
        },
        "events": events,
    }
