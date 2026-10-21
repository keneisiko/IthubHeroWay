"""Кто попадает в лидерборд: активированные студенты.

Раньше — только привязавшие Telegram. Привязали двое из 557, и после запуска
лидерборд был бы пустым при полном колледже. Аккаунт теперь активируется и
первым входом на сайт, поэтому критерий — активированный аккаунт.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class LeaderboardAudienceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        make = User.objects.create_user
        self.web = make(username="web", password="x", callsign="web", role=Role.AGENT, rating_current=Decimal("50"))
        self.asleep = make(username="asleep", password="x", callsign="asleep", role=Role.AGENT,
                           rating_current=Decimal("90"), is_active=False)
        self.curator = make(username="cur", password="x", callsign="cur", role=Role.CURATOR,
                            rating_current=Decimal("999"))
        self.client = APIClient()
        self.client.force_authenticate(self.web)

    def usernames(self):
        data = self.client.get("/api/v1/leaderboard/agents/", {"page_size": 50}).json()
        rows = data["results"] if isinstance(data, dict) else data
        return {row["username"] for row in rows}

    def test_activated_student_without_telegram_is_listed(self):
        self.assertIn("web", self.usernames())

    def test_not_activated_and_staff_are_not(self):
        names = self.usernames()

        self.assertNotIn("asleep", names, "ни разу не входил")
        self.assertNotIn("cur", names, "сотрудник не соревнуется со студентами")

    def test_rank_counts_the_same_people(self):
        """Место считается среди тех же, кто в списке: неактивный с 90 и
        куратор с 999 не должны отодвигать студента на третье место."""
        rank = self.client.get("/api/v1/rating/me/").json()["rank"]

        self.assertEqual(rank, 1)
