"""Каталог нашивок приходит на сайт целиком.

API по умолчанию отдаёт страницы по 20 записей, а сайт читает только первую.
На проде было 25 активных нашивок: пять студенты не видели, и новая нашивка,
добавленная в админке, всегда оказывалась среди невидимых — она последняя.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.badges.models import Badge, UserBadge
from apps.quests.models import Quest, QuestType, UserQuestProgress

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class FullListsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="s", password="x", callsign="s", role=Role.AGENT)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_new_badge_is_in_the_catalog_after_twenty(self):
        Badge.objects.bulk_create(
            Badge(code=f"b{i}", title=f"Нашивка {i}", condition={"manual": True}) for i in range(25)
        )
        newest = Badge.objects.create(code="fresh", title="Новая", condition={"manual": True})

        codes = [row["code"] for row in self.client.get("/api/v1/badges/").json()]

        self.assertEqual(len(codes), 26)
        self.assertIn(newest.code, codes)

    def test_all_earned_badges_are_listed(self):
        badges = Badge.objects.bulk_create(
            Badge(code=f"e{i}", title=f"Получена {i}", condition={"manual": True}) for i in range(22)
        )
        UserBadge.objects.bulk_create(UserBadge(user=self.user, badge=b) for b in badges)

        self.assertEqual(len(self.client.get("/api/v1/badges/my/").json()), 22)

    def test_completed_quests_are_all_returned(self):
        """По этому списку сайт решает, что квест выполнен: обрезка возвращала
        старые выполненные квесты в «активные»."""
        quests = Quest.objects.bulk_create(
            Quest(code=f"q{i}", title=f"Квест {i}", quest_type=QuestType.LONG) for i in range(23)
        )
        UserQuestProgress.objects.bulk_create(
            UserQuestProgress(user=self.user, quest=q, is_completed=True, progress_value=1) for q in quests
        )

        rows = self.client.get("/api/v1/quests/my-progress/", {"completed": "true"}).json()

        self.assertEqual(len(rows), 23)
