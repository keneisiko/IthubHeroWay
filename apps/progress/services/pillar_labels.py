"""UI-лейблы для опор (характеристик) на дашборде и в профиле."""

from __future__ import annotations

from apps.progress.models import Characteristic, CharacteristicHistory

UI_PILLARS: tuple[tuple[str, str], ...] = (
    ("rhythm", "Ритм"),
    ("discipline", "Фокус"),
    ("power", "Мощность"),
    ("teamwork", "Связь"),
    ("initiative", "Отдача"),
)

PILLAR_BY_LABEL = {label: pillar for pillar, label in UI_PILLARS}
LABEL_BY_PILLAR = {pillar: label for pillar, label in UI_PILLARS}


def skills_by_label(user) -> tuple[dict[str, float], dict[str, float]]:
    """Текущие и пиковые значения по UI-лейблам (шкала 0–20)."""
    pillars = [p for p, _ in UI_PILLARS]
    chars = {
        c.pillar: c
        for c in Characteristic.objects.filter(user=user, pillar__in=pillars)
    }
    skills: dict[str, float] = {}
    peaks: dict[str, float] = {}
    for pillar, label in UI_PILLARS:
        char = chars.get(pillar)
        skills[label] = round(char.current, 1) if char else 0.0
        peaks[label] = round(char.peak, 1) if char else 0.0
    return skills, peaks


def skills_percent_by_label(user) -> tuple[dict[str, int], dict[str, int]]:
    """Значения для радара дашборда (шкала 0–100)."""
    skills, peaks = skills_by_label(user)
    return (
        {label: min(100, round(val * 5)) for label, val in skills.items()},
        {label: min(100, round(val * 5)) for label, val in peaks.items()},
    )


def characteristics_payload(user) -> list[dict]:
    pillars = [p for p, _ in UI_PILLARS]
    chars = {
        c.pillar: c
        for c in Characteristic.objects.filter(user=user, pillar__in=pillars)
    }

    # Prefetch тут не помогал: любой `order_by`/срез на связи игнорирует
    # заготовленный кеш и уходит в новый запрос — получалось по запросу
    # на каждую из пяти опор, при этом prefetch грузил всю историю в память.
    # Берём последние точки одним запросом и раскладываем по опорам.
    history_by_char: dict[int, list[float]] = {}
    if chars:
        entries = (
            CharacteristicHistory.objects.filter(characteristic__in=chars.values())
            .order_by("characteristic_id", "-created_at")
            .values_list("characteristic_id", "value")
        )
        for characteristic_id, value in entries:
            bucket = history_by_char.setdefault(characteristic_id, [])
            if len(bucket) < 6:
                bucket.append(round(value, 1))

    result: list[dict] = []
    for pillar, label in UI_PILLARS:
        char = chars.get(pillar)
        current = round(char.current, 1) if char else 0.0
        peak = round(char.peak, 1) if char else 0.0
        history_values: list[float] = []
        if char:
            history_values = list(reversed(history_by_char.get(char.pk, [])))
        while len(history_values) < 6:
            history_values.insert(0, 0.0)
        result.append(
            {
                "pillar": pillar,
                "label": label,
                "current": current,
                "peak": peak,
                "history": history_values,
            }
        )
    return result
