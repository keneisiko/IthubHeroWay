"""Статусы рейтинга и прогресс до следующего статуса.

Границы и названия заданы разделом 8 Положения: Новобранец, Стажёр,
Специалист, Профи, Мастер, Легенда. Единственный источник — настройка
`POLOZHENIE_STATUSES`; раньше те же пороги были захардкожены ещё в двух
местах, в админке и на дашбордах, и при правке расходились.

Названия «зона» и `rating_zone` сохранены: по ним ходят сериализаторы,
админка и фронт. Меняется содержание шкалы, а не её интерфейс.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings

# Цвет на каждый статус. Самого цвета в Положении нет — это вопрос
# оформления, а не правил начисления.
ZONE_COLORS: dict[str, str] = {
    "recruit": "#d32f2f",
    "trainee": "#ef6c00",
    "specialist": "#f9a825",
    "pro": "#2e7d32",
    "master": "#1976d2",
    "legend": "#6a1b9a",
}


def _statuses() -> tuple[tuple[Decimal, str, str], ...]:
    """Шкала статусов из настроек, отсортированная по нижней границе."""
    raw = getattr(settings, "POLOZHENIE_STATUSES", ())
    return tuple(sorted(((Decimal(str(t)), c, label) for t, c, label in raw), key=lambda row: row[0]))


# Совместимость: часть кода ожидает кортеж (порог, код, название).
RATING_ZONES = _statuses()

ZONE_NAMES_RU: dict[str, str] = {code: label for _, code, label in RATING_ZONES}


def zone_bounds() -> list[tuple[str, Decimal, Decimal | None]]:
    """Границы статусов как (код, нижняя включительно, верхняя исключительно)."""
    scale = _statuses()
    bounds: list[tuple[str, Decimal, Decimal | None]] = []
    for idx, (threshold, code, _label) in enumerate(scale):
        upper = scale[idx + 1][0] if idx + 1 < len(scale) else None
        bounds.append((code, threshold, upper))
    return bounds


def rating_zone(rating) -> str:
    """Код статуса по текущему рейтингу (п. 8.1)."""
    value = Decimal(str(rating or 0))
    scale = _statuses()
    zone = scale[0][1]
    for threshold, code, _ in scale:
        if value >= threshold:
            zone = code
    return zone


def rating_status_label(rating) -> str:
    """Название статуса так, как оно звучит в Положении."""
    return ZONE_NAMES_RU.get(rating_zone(rating), "")


def rating_progress(rating) -> dict:
    value = Decimal(str(rating or 0))
    scale = _statuses()

    current_idx = 0
    for idx, (threshold, _code, _label) in enumerate(scale):
        if value >= threshold:
            current_idx = idx
    current_threshold, zone, zone_label = scale[current_idx]

    if current_idx + 1 < len(scale):
        next_threshold, next_zone, next_zone_label = scale[current_idx + 1]
        span = next_threshold - current_threshold
        points_to_next = max(Decimal("0"), next_threshold - value)
        progress_percent = (
            round(float((value - current_threshold) / span * 100), 1) if span else 100.0
        )
    else:
        # Легенда — последний статус, но рейтинг может расти дальше (п. 1.3),
        # поэтому прогресс остаётся полным, а не обнуляется.
        next_threshold = None
        next_zone = None
        next_zone_label = None
        points_to_next = Decimal("0")
        progress_percent = 100.0

    return {
        "zone": zone,
        "zone_label": zone_label,
        "next_zone": next_zone,
        "next_zone_label": next_zone_label,
        "points_to_next": float(points_to_next),
        "progress_percent": min(100.0, max(0.0, progress_percent)),
        "current_threshold": float(current_threshold),
        "next_threshold": float(next_threshold) if next_threshold is not None else None,
    }


def status_threshold(index: int) -> Decimal:
    """Нижняя граница статуса по его номеру в шкале (0 — самый низкий).

    Дашборды показывают «красную зону» и «список риска». Прежде их пороги
    были записаны числами 100 и 200 прямо в запросах, и после смены шкалы
    Положением 200 перестало быть границей чего-либо.
    """
    scale = _statuses()
    if not scale:
        return Decimal("0")
    index = max(0, min(index, len(scale) - 1))
    return scale[index][0]


def red_zone_max() -> Decimal:
    """Верхняя граница самого низкого статуса: с кем нужно разговаривать."""
    return status_threshold(1)


def risk_zone_max() -> Decimal:
    """Верхняя граница второго статуса: список риска у тьютора."""
    return status_threshold(2)
