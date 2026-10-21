"""Рамка аватара: нашивка с рамкой главнее купленной в магазине,
и одно и то же значение видно в профиле, рейтинге и отряде."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, Squad
from apps.badges.models import AvatarFrame, Badge, UserBadge
from apps.integrations.models import TelegramAccountLink
from apps.shop.models import Purchase, ShopItem, ShopItemType

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class AvatarFrameTests(TestCase):
    def setUp(self):
        cache.clear()
        self.squad = Squad.objects.create(code="alpha", name="Альфа")
        self.dev = User.objects.create_user(username="dev", password="x", callsign="dev", role=Role.AGENT, squad=self.squad)
        self.buyer = User.objects.create_user(username="buyer", password="x", callsign="buyer", role=Role.AGENT, squad=self.squad)
        self.plain = User.objects.create_user(username="plain", password="x", callsign="plain", role=Role.AGENT, squad=self.squad)
        for n, user in enumerate((self.dev, self.buyer, self.plain)):
            TelegramAccountLink.objects.create(user=user, telegram_user_id=760 + n, telegram_chat_id=760 + n, is_active=True)

        dev_badge = Badge.objects.create(
            code="dev", title="Разработчик", condition={"manual": True}, avatar_frame=AvatarFrame.DEVELOPER
        )
        UserBadge.objects.create(user=self.dev, badge=dev_badge)
        frame = ShopItem.objects.create(
            code="cosmetic-avatar-frame", title="Рамка", item_type=ShopItemType.COSMETIC, price_coins=30
        )
        # у разработчика куплена и фиолетовая — побеждает нашивка
        for user in (self.dev, self.buyer):
            Purchase.objects.create(user=user, item=frame, coins_spent=30, applied_at=timezone.now())

        self.client = APIClient()
        self.client.force_authenticate(self.plain)

    def test_profile_me_and_public(self):
        self.assertEqual(self.client.get("/api/v1/profile/me/").json()["avatar_frame"], "")
        self.assertEqual(self.client.get("/api/v1/profile/dev/").json()["avatar_frame"], "developer")
        self.assertEqual(self.client.get("/api/v1/profile/buyer/").json()["avatar_frame"], "purple")

    def test_leaderboard(self):
        rows = self.client.get("/api/v1/leaderboard/agents/").json()
        rows = rows.get("results", rows) if isinstance(rows, dict) else rows
        rows = {r["username"]: r["avatar_frame"] for r in rows}
        self.assertEqual(rows, {"dev": "developer", "buyer": "purple", "plain": ""})

    def test_squad_members(self):
        rows = self.client.get("/api/v1/squads/alpha/members/").json()
        rows = rows.get("results", rows) if isinstance(rows, dict) else rows
        rows = {r["username"]: r["avatar_frame"] for r in rows}
        self.assertEqual(rows, {"dev": "developer", "buyer": "purple", "plain": ""})
