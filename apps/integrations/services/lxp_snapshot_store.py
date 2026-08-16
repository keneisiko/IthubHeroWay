"""Сохранение снимков LXP с защитой от затирания.

`update_or_create(date=...)` перезаписывает снимок целиком. Если очередной
прогон вернул пустой или частичный результат (LXP отдал ошибку, токен протух,
выборка не собралась), валидные данные за эту дату молча заменялись пустыми —
и рейтинг после этого считался по пустому снимку.
"""

from __future__ import annotations

import logging
from datetime import date

from django.db import transaction

from apps.integrations.models import LXPSnapshot

logger = logging.getLogger(__name__)


def snapshot_payload_size(data: dict | None) -> int:
    """Сколько записей о студентах содержит снимок."""
    if not isinstance(data, dict):
        return 0

    def _rows(block) -> int:
        if isinstance(block, dict):
            inner = block.get("data") if "data" in block else block
            return len(inner) if isinstance(inner, dict) else 0
        return 0

    return _rows(data.get("grades")) + _rows(data.get("control_points")) + _rows(data.get("attendance"))


def is_partial(data: dict | None) -> bool:
    meta = (data or {}).get("meta") or {}
    return bool(meta.get("partial"))


@transaction.atomic
def save_snapshot(target_date: date, data: dict, *, force: bool = False) -> tuple[LXPSnapshot, bool]:
    """Сохранить снимок, не ухудшая уже сохранённые данные.

    Возвращает (снимок, было_ли_записано). Новый снимок отклоняется, если он
    пустой или частичный, а существующий — содержательнее.
    """
    existing = LXPSnapshot.objects.select_for_update().filter(date=target_date).first()

    if existing and not force:
        new_size = snapshot_payload_size(data)
        old_size = snapshot_payload_size(existing.data)

        if new_size == 0 and old_size > 0:
            logger.warning(
                "LXP snapshot %s: пустой результат не записан поверх снимка с %s записями",
                target_date,
                old_size,
            )
            return existing, False

        if is_partial(data) and not is_partial(existing.data) and new_size < old_size:
            logger.warning(
                "LXP snapshot %s: частичный результат (%s записей) не записан "
                "поверх полного (%s записей)",
                target_date,
                new_size,
                old_size,
            )
            return existing, False

    snapshot, _ = LXPSnapshot.objects.update_or_create(date=target_date, defaults={"data": data})
    return snapshot, True
