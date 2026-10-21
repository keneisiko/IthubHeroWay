"""Что видит другой студент в чужом профиле.

Раньше — только ник и карточку: статистику, нашивки и диаграмму
характеристик сервер для чужого профиля не отдавал. Точный рейтинг и
монеты по-прежнему скрыты (п. 11.1 Положения).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.badges.models import Badge, UserBadge
from apps.quests.models import Quest, QuestType, UserQuestProgress

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class PublicProfileContentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username="owner", password="x", callsign="owner", role=Role.AGENT)
        self.viewer = User.objects.create_user(username="viewer", password="x", callsign="viewer", role=Role.AGENT)
        self.client = APIClient()
        self.client.force_authenticate(self.viewer)
        badge = Badge.objects.create(code="intern", title="Стажировка", condition={"manual": True})
        UserBadge.objects.create(user=self.owner, badge=badge, is_pinned=True, source="manual:boss")
        quest = Quest.objects.create(code="q", title="Квест", quest_type=QuestType.LONG)
        UserQuestProgress.objects.create(user=self.owner, quest=quest, is_completed=True, progress_value=1)

    def data(self) -> dict:
        return self.client.get("/api/v1/profile/owner/").json()

    def test_stats_badges_and_chart_are_visible(self):
        data = self.data()

        self.assertEqual(data["quests_completed"], 1)
        self.assertEqual([row["badge"]["code"] for row in data["badges"]], ["intern"])
        self.assertTrue(data["badges"][0]["is_pinned"])
        self.assertEqual(len(data["characteristics"]), 5, "все оси диаграммы, даже нулевые")

    def test_who_awarded_the_badge_is_not_exposed(self):
        """В source лежит логин выдавшего сотрудника."""
        self.assertNotIn("source", self.data()["badges"][0])

    def test_exact_rating_and_coins_stay_hidden(self):
        data = self.data()

        self.assertIsNone(data["rating_current"])
        self.assertNotIn("coins_balance", data)
