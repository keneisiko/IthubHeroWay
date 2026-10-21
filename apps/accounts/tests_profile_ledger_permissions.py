from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.shop.models import ShopItem

User = get_user_model()


class ProfileLedgerWriteProtectionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ledger-student",
            callsign="Before",
            password=None,
            role="agent",
            rating_current=Decimal("123.45"),
            coins_balance=Decimal("10.25"),
            level=3,
        )
        self.client.force_authenticate(self.user)

    def assert_ledger_unchanged(self):
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("123.45"))
        self.assertEqual(self.user.coins_balance, Decimal("10.25"))
        self.assertEqual(self.user.level, 3)

    def test_patch_preserves_ledger_and_still_updates_profile_fields(self):
        response = self.client.patch(
            reverse("profile-me"),
            {
                "username": "renamed-student",
                "callsign": "After",
                "rating_current": "99999.99",
                "coins_balance": "99999.99",
                "level": 99,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assert_ledger_unchanged()
        self.assertEqual(self.user.username, "renamed-student")
        self.assertEqual(self.user.callsign, "After")

    def test_put_preserves_ledger_and_still_updates_profile_fields(self):
        response = self.client.put(
            reverse("profile-me"),
            {
                "username": "renamed-student",
                "callsign": "After",
                "rating_current": "99999.99",
                "coins_balance": "99999.99",
                "level": 99,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assert_ledger_unchanged()
        self.assertEqual(self.user.username, "renamed-student")
        self.assertEqual(self.user.callsign, "After")

    def test_forged_balance_cannot_fund_a_purchase(self):
        item = ShopItem.objects.create(code="expensive", title="Expensive", price_coins=50)
        self.client.patch(reverse("profile-me"), {"coins_balance": "1000"}, format="json")

        response = self.client.post(reverse("shop-purchase"), {"item_code": item.code}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.user.purchases.exists())
        self.assert_ledger_unchanged()
