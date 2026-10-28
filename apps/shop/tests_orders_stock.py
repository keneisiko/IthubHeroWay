"""Остатки товаров и статусы заказов мерча и услуг."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.operations.models import PlatformSettings
from apps.operations.services.platform_settings import invalidate
from apps.shop.models import OrderStatus, Purchase, ShopItem, ShopItemSlot, ShopItemType
from apps.shop.services import advance_orders

User = get_user_model()


def make_user(username: str, coins: int = 500, **extra) -> User:
    return User.objects.create_user(
        username=username, password="x", callsign=f"call_{username}", coins_balance=coins, **extra
    )


def merch(code: str = "merch-cap", stock: int | None = None, price: int = 50) -> ShopItem:
    return ShopItem.objects.create(
        code=code, title=code, item_type=ShopItemType.OTHER, price_coins=price, stock=stock
    )


class StockTests(APITestCase):
    def setUp(self):
        self.user = make_user("buyer", role=Role.AGENT)
        self.client.force_authenticate(self.user)

    def buy(self, code: str):
        return self.client.post(reverse("shop-purchase"), {"item_code": code}, format="json")

    def test_purchase_decrements_stock_and_sold_out_item_disappears(self):
        merch(stock=1)
        self.assertEqual(self.buy("merch-cap").status_code, 201)
        self.assertEqual(ShopItem.objects.get(code="merch-cap").stock, 0)
        codes = [row["code"] for row in self.client.get(reverse("shop-items")).json()]
        self.assertNotIn("merch-cap", codes)

    def test_sold_out_purchase_refused_without_charging(self):
        merch(stock=0)
        response = self.buy("merch-cap")
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.coins_balance, 500)
        self.assertFalse(Purchase.objects.exists())

    def test_empty_stock_means_unlimited(self):
        merch(stock=None)
        self.assertEqual(self.buy("merch-cap").status_code, 201)
        self.assertEqual(self.buy("merch-cap").status_code, 201)
        self.assertIsNone(ShopItem.objects.get(code="merch-cap").stock)

    def test_merch_order_starts_as_ordered_cosmetic_has_no_status(self):
        merch()
        ShopItem.objects.create(
            code="frame", title="frame", item_type=ShopItemType.COSMETIC,
            slot=ShopItemSlot.AVATAR_FRAME, price_coins=10,
        )
        self.assertEqual(self.buy("merch-cap").json()["status"], OrderStatus.ORDERED)
        self.assertEqual(self.buy("frame").json()["status"], OrderStatus.NONE)

    def test_pickup_info_shown_on_open_order(self):
        PlatformSettings.objects.filter(pk=PlatformSettings.SINGLETON_PK).update(
            shop_pickup_info="Каб. 101, пн–пт 14:00"
        )
        invalidate()
        merch()
        self.assertEqual(self.buy("merch-cap").json()["pickup_info"], "Каб. 101, пн–пт 14:00")


class AdvanceOrdersTests(TestCase):
    def setUp(self):
        self.staff = make_user("staff", role=Role.ADMIN)
        self.student = make_user("st", role=Role.AGENT)
        self.order = Purchase.objects.create(
            user=self.student, item=merch(), coins_spent=50, status=OrderStatus.ORDERED
        )

    def test_order_goes_forward_and_records_who_issued(self):
        advance_orders(Purchase.objects.all(), OrderStatus.READY, self.staff)
        advance_orders(Purchase.objects.all(), OrderStatus.ISSUED, self.staff)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.ISSUED)
        self.assertEqual(self.order.issued_by, self.staff)

    def test_issued_order_cannot_go_back(self):
        advance_orders(Purchase.objects.all(), OrderStatus.ISSUED, self.staff)
        moved = advance_orders(Purchase.objects.all(), OrderStatus.READY, self.staff)
        self.assertEqual(moved, [])

    def test_cosmetic_purchase_is_skipped(self):
        cosmetic = Purchase.objects.create(
            user=self.student, item=merch("frame"), coins_spent=1, status=OrderStatus.NONE
        )
        advance_orders(Purchase.objects.filter(pk=cosmetic.pk), OrderStatus.ISSUED, self.staff)
        cosmetic.refresh_from_db()
        self.assertEqual(cosmetic.status, OrderStatus.NONE)

    @patch("apps.shop.admin.order_ready", return_value=1)
    def test_admin_ready_action_notifies_student(self, notify):
        root = User.objects.create_superuser(
            username="root", password="x", callsign="root", role=Role.ADMIN
        )
        self.client.force_login(root)
        self.client.post(
            reverse("admin:shop_purchase_changelist"),
            {"action": "mark_ready", "_selected_action": [self.order.pk]},
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.READY)
        notify.assert_called_once()
