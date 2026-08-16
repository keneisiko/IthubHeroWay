"""Формат снимка LXP: разбор блоков категорий.

Снимок хранит категории (`grades`, `control_points`, `attendance`) в двух видах:

    {"ok": true, "data": {<lxp_user_id>: {...}}}   — с отметкой успеха
    {<lxp_user_id>: {...}}                         — плоский словарь

Функция распаковки была продублирована в четырёх модулях под тремя разными
именами. Держим её в одном месте: при изменении формата снимка править
придётся ровно одно место.
"""

from __future__ import annotations


def unwrap_category(block: dict | None) -> dict:
    """Вернуть словарь «lxp_user_id → данные» независимо от формы блока."""
    if isinstance(block, dict) and "data" in block:
        inner = block.get("data")
        return inner if isinstance(inner, dict) else {}
    return block if isinstance(block, dict) else {}


def category_is_ok(block: dict | None) -> bool:
    """Отметил ли сборщик снимка эту категорию как успешно собранную."""
    return bool(isinstance(block, dict) and block.get("ok"))


def snapshot_row(data: dict | None, category: str, lxp_uid: str) -> dict | None:
    """Данные конкретного студента по категории снимка."""
    row = unwrap_category((data or {}).get(category)).get(lxp_uid)
    return row if isinstance(row, dict) else None
