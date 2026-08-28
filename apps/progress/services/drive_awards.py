"""Начисления за «Движ»: мероприятия, олимпиады, проекты, волонтёрство.

Коэффициенты `RATING_DRIVE` были описаны в регламенте и заведены в настройках,
но в коде не использовались нигде — единственный крупный источник рейтинга
«за заслуги» просто не был подключён. Из-за этого рейтинг целиком определялся
учебной гигиеной, а вся внеучебная активность на него не влияла.

Начисление идемпотентно по тройке «студент + код + дата»: повторный клик
в админке или повторный импорт списка участников ничего не удвоит.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.progress.models import RatingChangeSource, RatingLog
from apps.progress.services.rewards import apply_rating_delta_with_cap


class UnknownDriveCode(ValueError):
    pass


@dataclass(frozen=True)
class DriveAwardResult:
    granted: int
    skipped_duplicate: int
    points_each: int


def available_codes() -> dict[str, int]:
    return dict(getattr(settings, "RATING_DRIVE", {}))


def drive_source_id(code: str, day: date) -> str:
    return f"drive:{code}:{day.isoformat()}"


def grant_drive_award(user, code: str, *, day: date | None = None, note: str = "") -> int:
    """Начислить студенту баллы за активность. Возвращает применённую дельту."""
    points = available_codes().get(code)
    if points is None:
        raise UnknownDriveCode(f"Неизвестный код начисления: {code}")

    day = day or timezone.localdate()
    source_id = drive_source_id(code, day)

    with transaction.atomic():
        if RatingLog.objects.filter(user=user, source_id=source_id).exists():
            return 0
        reason = f"Движ: {code}"
        if note:
            reason = f"{reason} ({note})"
        return apply_rating_delta_with_cap(
            user=user,
            delta=int(points),
            source=RatingChangeSource.DRIVE,
            reason=reason[:250],
            source_id=source_id,
        )


def grant_drive_award_bulk(users, code: str, *, day: date | None = None, note: str = "") -> DriveAwardResult:
    points = available_codes().get(code)
    if points is None:
        raise UnknownDriveCode(f"Неизвестный код начисления: {code}")

    granted = 0
    duplicates = 0
    for user in users:
        applied = grant_drive_award(user, code, day=day, note=note)
        if applied:
            granted += 1
        else:
            duplicates += 1
    return DriveAwardResult(granted=granted, skipped_duplicate=duplicates, points_each=int(points))
