"""Рамка аватара: какую рисовать интерфейсу.

Нашивка с рамкой (например, «Разработчик») главнее купленной в
магазине: её не снять и не купить. Интерфейс получает одно поле —
код рамки или пустую строку.
"""

from __future__ import annotations

from django.db.models import OuterRef, Subquery

AVATAR_FRAME_ITEM = "cosmetic-avatar-frame"
PURPLE = "purple"
# Код товара-рамки → код рамки, которую рисует интерфейс.
FRAME_BY_ITEM: dict[str, str] = {
    AVATAR_FRAME_ITEM: PURPLE,
    "cosmetic-frame-gold": "gold",
    "cosmetic-frame-neon": "neon",
    "cosmetic-frame-flame": "flame",
}


def badge_frame_subquery():
    """Подзапрос для annotate: рамка от полученной нашивки или NULL."""
    from apps.badges.models import UserBadge

    return Subquery(
        UserBadge.objects.filter(user=OuterRef("pk"))
        .exclude(badge__avatar_frame="")
        .order_by("acquired_at")
        .values("badge__avatar_frame")[:1]
    )


def resolve_frame(badge_frame: str | None, applied_cosmetic: str | None) -> str:
    if badge_frame:
        return badge_frame
    return FRAME_BY_ITEM.get(applied_cosmetic or "", "")


def avatar_frame_for(user) -> str:
    from apps.badges.models import UserBadge
    from apps.shop.services import applied_purchases

    badge_frame = (
        UserBadge.objects.filter(user=user)
        .exclude(badge__avatar_frame="")
        .order_by("acquired_at")
        .values_list("badge__avatar_frame", flat=True)
        .first()
    )
    return resolve_frame(badge_frame, applied_purchases(user).get("avatar_frame"))
