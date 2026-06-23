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


def rating_zone(rating: int) -> str:
    zone = RATING_ZONES[0][1]
    for threshold, code, _ in RATING_ZONES:
        if rating >= threshold:
            zone = code
    return zone


def rating_progress(rating: int) -> dict:
    current_idx = 0
    for idx, (threshold, code, label) in enumerate(RATING_ZONES):
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
