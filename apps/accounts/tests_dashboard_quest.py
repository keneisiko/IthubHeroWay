"""Карточка «Активный квест» на дашборде.

Квест выбирался как первый активный по id, поэтому на карточке висел
вчерашний выпуск ежедневного квеста, пока сегодняшний лежал в списке квестов.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.quests.models import Quest, QuestType, UserQuestProgress

User = get_user_model()


class DashboardCurrentQuestTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="agent",
            email="agent@test.ru",
            password="x",
            callsign="Агент",
            role=Role.AGENT,
        )
        self.client.force_authenticate(self.user)
        self.today = timezone.localdate()

    def make_quest(self, code: str, day) -> Quest:
        start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
        return Quest.objects.create(
            code=code,
            title=code,
            quest_type=QuestType.DAILY,
            period_key=day.isoformat(),
            start_at=start,
            end_at=start + timedelta(days=1),
        )

    def current_code(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        quest = response.data["current_quest"]
        return quest["code"] if quest else None

    def test_yesterdays_issue_does_not_stay_on_the_card(self):
        self.make_quest("daily:yesterday", self.today - timedelta(days=1))
        self.make_quest("daily:today", self.today)

        self.assertEqual(self.current_code(), "daily:today")

    def test_completed_quest_gives_way_to_the_next_one(self):
        done = self.make_quest("daily:done", self.today)
        self.make_quest("daily:next", self.today)
        UserQuestProgress.objects.create(user=self.user, quest=done, is_completed=True)

        self.assertEqual(self.current_code(), "daily:next")
