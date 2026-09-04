"""Применение покупок.

Купленный предмет сам по себе ничего не менял: кнопка «Применить» в интерфейсе
показывала тост «пока не подключено на бэкенде». Здесь живёт правило, которое
делает её осмысленной — активной может быть одна покупка на тип товара.
Иначе у студента одновременно «надеты» три рамки аватара, и какая из них
показывается, зависит от порядка выборки.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.shop.models import Purchase


class PurchaseNotOwned(LookupError):
    pass


@transaction.atomic
def apply_purchase(user, purchase_id: int) -> Purchase:
    """Сделать покупку активной, сняв прежнюю активную того же типа."""
    try:
        purchase = (
            Purchase.objects.select_for_update()
            .select_related("item")
            .get(pk=purchase_id, user=user)
        )
    except Purchase.DoesNotExist as exc:
        raise PurchaseNotOwned("Покупка не найдена у этого пользователя.") from exc

    if purchase.applied_at:
        return purchase

    Purchase.objects.filter(
        user=user, item__item_type=purchase.item.item_type, applied_at__isnull=False
    ).exclude(pk=purchase.pk).update(applied_at=None)

    purchase.applied_at = timezone.now()
    purchase.save(update_fields=["applied_at"])
    return purchase


@transaction.atomic
def unapply_purchase(user, purchase_id: int) -> Purchase:
    """Снять покупку: у студента должна быть возможность вернуть вид по умолчанию."""
    try:
        purchase = Purchase.objects.select_for_update().get(pk=purchase_id, user=user)
    except Purchase.DoesNotExist as exc:
        raise PurchaseNotOwned("Покупка не найдена у этого пользователя.") from exc

    if purchase.applied_at:
        purchase.applied_at = None
        purchase.save(update_fields=["applied_at"])
    return purchase


def applied_purchases(user) -> dict[str, str]:
    """Активные покупки студента: тип товара → код предмета.

    В таком виде их удобно отдавать профилю: интерфейсу нужно знать, какую
    рамку и какое свечение рисовать, а не весь список покупок.
    """
    rows = (
        Purchase.objects.filter(user=user, applied_at__isnull=False)
        .select_related("item")
        .order_by("item__item_type", "-applied_at")
    )
    return {row.item.item_type: row.item.code for row in rows}
