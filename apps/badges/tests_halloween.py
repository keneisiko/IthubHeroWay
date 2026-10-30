"""Нашивка «Самый страшный»: заводится миграцией и даёт рамку-склеп."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, Squad
from apps.badges.models import AvatarFrame, Badge, UserBadge
from apps.integrations.models import TelegramAccountLink

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class HalloweenBadgeTests(TestCase):
    def setUp(self):
        cache.clear()
        squad = Squad.objects.create(code="alpha", name="Альфа")
        self.agent = User.objects.create_user(username="ghoul", password="x", callsign="Гуль", role=Role.AGENT, squad=squad)
        TelegramAccountLink.objects.create(user=self.agent, telegram_user_id=771, telegram_chat_id=771, is_active=True)
        self.client = APIClient()
        self.client.force_authenticate(self.agent)
        self.badge = Badge.objects.get(code="halloween-scariest")

    def test_migration_creates_manual_badge_with_frame(self):
        self.assertEqual(self.badge.title, "Самый страшный")
        self.assertEqual(self.badge.avatar_frame, AvatarFrame.HALLOWEEN)
        self.assertEqual(self.badge.condition, {"manual": True})

    def test_catalog_tells_which_badges_change_the_profile(self):
        rows = self.client.get("/api/v1/badges/").json()
        rows = rows["results"] if isinstance(rows, dict) else rows
        frames = {row["code"]: row["avatar_frame"] for row in rows}
        self.assertEqual(frames["halloween-scariest"], "halloween")

    def test_pinned_badge_gives_halloween_frame(self):
        self.assertEqual(self.client.get("/api/v1/profile/me/").json()["avatar_frame"], "")
        UserBadge.objects.create(user=self.agent, badge=self.badge, is_pinned=True)
        cache.clear()
        self.assertEqual(self.client.get("/api/v1/profile/me/").json()["avatar_frame"], "halloween")
