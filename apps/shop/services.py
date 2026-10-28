"""Применение покупок.

Купленный предмет сам по себе ничего не менял: кнопка «Применить» в интерфейсе
показывала тост «пока не подключено на бэкенде». Здесь живёт правило, которое
делает её осмысленной — активной может быть одна покупка на слот товара
(рамка, свечение, баннер независимы друг от друга).
Иначе у студента одновременно «надеты» три рамки аватара, и какая из них
показывается, зависит от порядка выборки.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.shop.models import (
    BOOST_QUEST_X2_CODE,
    COSMETIC_SLOTS,
    FULFILLED_TYPES,
    OrderStatus,
    Purchase,
    ShopItemSlot,
)


class PurchaseNotOwned(LookupError):
    pass


class PurchaseNotApplicable(ValueError):
    pass


def unused_boosts(user):
    """Неиспользованные рабочие бусты студента.

    Фильтр по слоту и коду, а не по типу: старые покупки снятых «Буст опыта» и
    «Двойные монеты» имеют тип boost, но ничего не делали и работать не должны.
    """
    return Purchase.objects.filter(
        user=user,
        item__slot=ShopItemSlot.BOOST,
        item__code=BOOST_QUEST_X2_CODE,
        consumed_at__isnull=True,
    )


@transaction.atomic
def apply_purchase(user, purchase_id: int) -> Purchase:
    """Сделать покупку активной, сняв прежнюю активную того же слота."""
    # Блокировка пользователя сериализует параллельные «применить» двух предметов
    # одного слота: иначе оба видят друг друга неактивными и остаются надетыми.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    try:
        purchase = (
            Purchase.objects.select_for_update()
            .select_related("item")
            .get(pk=purchase_id, user=user)
        )
    except Purchase.DoesNotExist as exc:
        raise PurchaseNotOwned("Покупка не найдена у этого пользователя.") from exc

    item = purchase.item
    # Буст не надевается: он срабатывает сам на следующей награде за квест.
    if item.slot == ShopItemSlot.BOOST:
        raise PurchaseNotApplicable("Буст нельзя надеть: он сработает сам на награде за следующий квест.")
    if item.slot not in COSMETIC_SLOTS:
        raise PurchaseNotApplicable("Этот предмет нельзя применить.")

    if purchase.applied_at:
        return purchase

    Purchase.objects.filter(user=user, applied_at__isnull=False, item__slot=item.slot).exclude(pk=purchase.pk).update(applied_at=None)

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
    """Активные покупки студента: слот → код предмета (только косметические слоты).

    В таком виде их удобно отдавать профилю: интерфейсу нужно знать, какую
    рамку, свечение и баннер рисовать, а не весь список покупок.
    """
    rows = (
        Purchase.objects.filter(user=user, applied_at__isnull=False, item__slot__in=COSMETIC_SLOTS)
        .select_related("item")
        .order_by("applied_at")
    )
    # Порядок по возрастанию: при сбое «двух на слот» побеждает самая свежая.
    return {row.item.slot: row.item.code for row in rows}


def active_boost(user) -> Purchase | None:
    """Неиспользованный буст студента (самый ранний)."""
    return (
        unused_boosts(user)
        .select_related("item")
        .order_by("created_at", "id")
        .first()
    )


# Заказ двигается только вперёд: «выдан» нельзя вернуть в «готов», иначе
# сотрудник мог бы выдать одну вещь дважды.
NEXT_STATUS: dict[str, tuple[str, ...]] = {
    OrderStatus.ORDERED: (OrderStatus.READY, OrderStatus.ISSUED),
    OrderStatus.READY: (OrderStatus.ISSUED,),
    OrderStatus.ISSUED: (),
}


def initial_status(item) -> str:
    return OrderStatus.ORDERED if item.item_type in FULFILLED_TYPES else OrderStatus.NONE


@transaction.atomic
def advance_orders(queryset, target: str, staff) -> list[Purchase]:
    """Перевести заказы в статус target; возвращает те, что действительно сдвинулись."""
    moved: list[Purchase] = []
    now = timezone.now()
    for purchase in queryset.select_for_update().select_related("item", "user"):
        if target not in NEXT_STATUS.get(purchase.status, ()):
            continue
        purchase.status = target
        purchase.status_changed_at = now
        fields = ["status", "status_changed_at"]
        if target == OrderStatus.ISSUED:
            purchase.issued_by = staff
            fields.append("issued_by")
        purchase.save(update_fields=fields)
        moved.append(purchase)
    return moved
