"""Кто получил нашивку: список владельцев в карточке нашивки."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, Squad
from apps.badges.models import AvatarFrame, Badge, UserBadge
from apps.integrations.models import TelegramAccountLink

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class BadgeHoldersTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="alpha", name="Альфа")
        self.first = User.objects.create_user(username="first", password="x", callsign="Первый", role=Role.AGENT, squad=self.squad)
        self.second = User.objects.create_user(username="second", password="x", callsign="Второй", role=Role.AGENT, squad=self.squad)
        self.viewer = User.objects.create_user(username="viewer", password="x", callsign="Зритель", role=Role.AGENT, squad=self.squad)
        self.gone = User.objects.create_user(username="gone", password="x", callsign="Ушёл", role=Role.AGENT, is_active=False)
        self.staff = User.objects.create_user(username="staff", password="x", callsign="Куратор", role=Role.CURATOR)
        for n, user in enumerate((self.first, self.second, self.viewer)):
            TelegramAccountLink.objects.create(user=user, telegram_user_id=880 + n, telegram_chat_id=880 + n, is_active=True)

        self.badge = Badge.objects.create(code="dev", title="Разработчик", condition={"manual": True}, avatar_frame=AvatarFrame.DEVELOPER)
        now = timezone.now()
        for user, days_ago in ((self.second, 1), (self.first, 5), (self.gone, 3), (self.staff, 2)):
            # рамка разработчика — только у закрепившего нашивку
            ub = UserBadge.objects.create(user=user, badge=self.badge, is_pinned=user is self.first)
            UserBadge.objects.filter(pk=ub.pk).update(acquired_at=now - timedelta(days=days_ago))

        self.client = APIClient()
        self.client.force_authenticate(self.viewer)

    def test_lists_active_agents_first_earned_first(self):
        res = self.client.get("/api/v1/badges/dev/holders/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual([r["username"] for r in data["results"]], ["first", "second"])
        row = data["results"][0]
        self.assertEqual(row["callsign"], "Первый")
        self.assertEqual(row["squad"], "Альфа")
        self.assertEqual(row["avatar_frame"], "developer")
        self.assertEqual(data["results"][1]["avatar_frame"], "")
        self.assertIn("acquired_at", row)
        # чужие закрытые данные в списке не светятся
        self.assertNotIn("rating_current", row)
        self.assertNotIn("source", row)

    def test_empty_badge(self):
        Badge.objects.create(code="rare", title="Редкая", condition={"manual": True})
        data = self.client.get("/api/v1/badges/rare/holders/").json()
        self.assertEqual(data, {"count": 0, "results": []})

    def test_unknown_or_inactive_badge(self):
        self.assertEqual(self.client.get("/api/v1/badges/nope/holders/").status_code, 404)
        Badge.objects.create(code="old", title="Старая", condition={}, is_active=False)
        self.assertEqual(self.client.get("/api/v1/badges/old/holders/").status_code, 404)

    def test_requires_login(self):
        self.assertIn(APIClient().get("/api/v1/badges/dev/holders/").status_code, (401, 403))
