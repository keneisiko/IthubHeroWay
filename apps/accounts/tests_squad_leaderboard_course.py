"""Рейтинг отрядов слушается фильтра по курсу, как и рейтинг агентов."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, Squad
from apps.integrations.models import TelegramAccountLink

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class SquadLeaderboardCourseTests(TestCase):
    def setUp(self):
        cache.clear()
        self.first = Squad.objects.create(code="pi-11", name="ПИ-11", course=1)
        self.third = Squad.objects.create(code="pi-31", name="ПИ-31", course=3)
        for n, squad in enumerate((self.first, self.third)):
            user = User.objects.create_user(
                username=f"agent{n}", password="x", callsign=f"Агент {n}", role=Role.AGENT, squad=squad
            )
            TelegramAccountLink.objects.create(user=user, telegram_user_id=990 + n, telegram_chat_id=990 + n, is_active=True)
        self.client = APIClient()
        self.client.force_authenticate(User.objects.get(username="agent0"))

    def codes(self, **params):
        res = self.client.get("/api/v1/squads/leaderboard/", params)
        self.assertEqual(res.status_code, 200)
        return sorted(row["code"] for row in res.json())

    def test_without_course_all_squads(self):
        self.assertEqual(self.codes(), ["pi-11", "pi-31"])

    def test_course_filters_squads(self):
        self.assertEqual(self.codes(course=3), ["pi-31"])
        self.assertEqual(self.codes(course=1), ["pi-11"])

    def test_course_is_part_of_cache_key(self):
        self.codes(course=3)
        self.assertEqual(self.codes(), ["pi-11", "pi-31"])

    def test_bad_course_is_ignored(self):
        self.assertEqual(self.codes(course="abc"), ["pi-11", "pi-31"])
