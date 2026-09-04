"""Применение покупок.

Кнопка «Применить» в интерфейсе показывала тост «пока не подключено
на бэкенде»: купленный предмет ни на что не влиял.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.shop.models import Purchase, ShopItem, ShopItemType
from apps.shop.services import PurchaseNotOwned, applied_purchases, apply_purchase, unapply_purchase

User = get_user_model()


def make_agent(username: str) -> User:
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.ru",
        password="x",
        callsign=f"call_{username}",
        role=Role.AGENT,
        coins_balance=500,
    )


def make_item(code: str, item_type: str = ShopItemType.COSMETIC) -> ShopItem:
    return ShopItem.objects.create(
        code=code, title=code, item_type=item_type, price_coins=10, is_active=True
    )


class ApplyPurchaseServiceTests(TestCase):
    def setUp(self):
        self.user = make_agent("shopper")
        self.frame = Purchase.objects.create(
            user=self.user, item=make_item("frame-violet"), coins_spent=10
        )
        self.glow = Purchase.objects.create(
            user=self.user, item=make_item("badge-glow"), coins_spent=10
        )

    def test_apply_marks_purchase_active(self):
        purchase = apply_purchase(self.user, self.frame.pk)

        self.assertIsNotNone(purchase.applied_at)
        self.assertTrue(purchase.is_applied)

    def test_only_one_purchase_per_type_stays_applied(self):
        """Иначе на студенте одновременно «надеты» две рамки аватара."""
        apply_purchase(self.user, self.frame.pk)
        apply_purchase(self.user, self.glow.pk)

        self.frame.refresh_from_db()
        self.glow.refresh_from_db()
        self.assertIsNone(self.frame.applied_at)
        self.assertIsNotNone(self.glow.applied_at)

    def test_purchases_of_different_types_coexist(self):
        boost = Purchase.objects.create(
            user=self.user, item=make_item("boost-x2", ShopItemType.BOOST), coins_spent=10
        )

        apply_purchase(self.user, self.frame.pk)
        apply_purchase(self.user, boost.pk)

        self.frame.refresh_from_db()
        boost.refresh_from_db()
        self.assertIsNotNone(self.frame.applied_at)
        self.assertIsNotNone(boost.applied_at)
        self.assertEqual(
            applied_purchases(self.user),
            {ShopItemType.COSMETIC: "frame-violet", ShopItemType.BOOST: "boost-x2"},
        )

    def test_apply_twice_is_idempotent(self):
        first = apply_purchase(self.user, self.frame.pk)
        second = apply_purchase(self.user, self.frame.pk)

        self.assertEqual(first.applied_at, second.applied_at)

    def test_unapply_returns_default_look(self):
        apply_purchase(self.user, self.frame.pk)
        unapply_purchase(self.user, self.frame.pk)

        self.frame.refresh_from_db()
        self.assertIsNone(self.frame.applied_at)
        self.assertEqual(applied_purchases(self.user), {})

    def test_foreign_purchase_is_rejected(self):
        stranger = make_agent("stranger")
        with self.assertRaises(PurchaseNotOwned):
            apply_purchase(stranger, self.frame.pk)


class ApplyPurchaseApiTests(APITestCase):
    """Аутентификация в API — JWT, поэтому force_authenticate, а не force_login."""

    def setUp(self):
        self.user = make_agent("api_shopper")
        self.client.force_authenticate(self.user)
        self.purchase = Purchase.objects.create(
            user=self.user, item=make_item("frame-gold"), coins_spent=10
        )

    def _url(self, purchase_id: int) -> str:
        return reverse("shop-purchase-apply", args=[purchase_id])

    def test_post_applies_and_delete_removes(self):
        response = self.client.post(self._url(self.purchase.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_applied"])

        response = self.client.delete(self._url(self.purchase.pk))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_applied"])

    def test_foreign_purchase_returns_404(self):
        other = Purchase.objects.create(
            user=make_agent("other_shopper"), item=make_item("frame-blue"), coins_spent=10
        )

        response = self.client.post(self._url(other.pk))

        self.assertEqual(response.status_code, 404)

    def test_my_purchases_expose_applied_state(self):
        apply_purchase(self.user, self.purchase.pk)

        response = self.client.get(reverse("shop-my-purchases"))

        self.assertEqual(response.status_code, 200)
        rows = response.json()["results"]
        self.assertTrue(rows[0]["is_applied"])
