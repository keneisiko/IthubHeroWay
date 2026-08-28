"""Зоны рейтинга и прогресс до следующей зоны."""

from __future__ import annotations

RATING_ZONES: tuple[tuple[int, str, str], ...] = (
    (0, "red", "Старт"),
    (100, "orange", "Новичок"),
    (200, "yellow", "Игрок"),
    (400, "green", "Профи"),
    (650, "platinum", "Лидер"),
    (850, "gold", "Элита"),
)

# Единственный источник границ зон. Раньше те же пороги были захардкожены
# ещё в двух местах — в админке и на дашбордах, — и при правке расходились.
ZONE_NAMES_RU: dict[str, str] = {
    "red": "Красная",
    "orange": "Оранжевая",
    "yellow": "Жёлтая",
    "green": "Зелёная",
    "platinum": "Платиновая",
    "gold": "Золотая",
}

ZONE_COLORS: dict[str, str] = {
    "red": "#d32f2f",
    "orange": "#ef6c00",
    "yellow": "#f9a825",
    "green": "#2e7d32",
    "platinum": "#1976d2",
    "gold": "#6a1b9a",
}


def zone_bounds() -> list[tuple[str, int, int | None]]:
    """Границы зон как (код, нижняя граница включительно, верхняя исключительно)."""
    bounds: list[tuple[str, int, int | None]] = []
    for idx, (threshold, code, _label) in enumerate(RATING_ZONES):
        upper = RATING_ZONES[idx + 1][0] if idx + 1 < len(RATING_ZONES) else None
        bounds.append((code, threshold, upper))
    return bounds


def rating_zone(rating: int) -> str:
    zone = RATING_ZONES[0][1]
    for threshold, code, _ in RATING_ZONES:
        if rating >= threshold:
            zone = code
    return zone


def rating_progress(rating: int) -> dict:
    current_idx = 0
    for idx, (threshold, _code, _label) in enumerate(RATING_ZONES):
        if rating >= threshold:
            current_idx = idx
    current_threshold, zone, zone_label = RATING_ZONES[current_idx]
    if current_idx + 1 < len(RATING_ZONES):
        next_threshold, next_zone, next_zone_label = RATING_ZONES[current_idx + 1]
        span = next_threshold - current_threshold
        points_to_next = max(0, next_threshold - rating)
        progress_percent = round((rating - current_threshold) / span * 100, 1) if span else 100.0
    else:
        next_threshold = None
        next_zone = None
        next_zone_label = None
        points_to_next = 0
        progress_percent = 100.0

    return {
        "zone": zone,
        "zone_label": zone_label,
        "next_zone": next_zone,
        "next_zone_label": next_zone_label,
        "points_to_next": points_to_next,
        "progress_percent": min(100.0, max(0.0, progress_percent)),
        "current_threshold": current_threshold,
        "next_threshold": next_threshold,
    }
