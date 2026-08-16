"""Тесты выдачи значков — модуль не имел покрытия вовсе."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Role
from apps.badges.models import Badge, UserBadge
from apps.badges.services import award_badges_for_user
from apps.badges.tasks import check_badges_weekly
from apps.integrations.models import TelegramAccountLink
from apps.quests.models import Quest, UserQuestProgress

User = get_user_model()


class AwardBadgesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="hero",
            email="hero@nalchik.ithub.ru",
            password="x",
            callsign="hero_call",
            role=Role.AGENT,
        )
        self.badge = Badge.objects.create(
            code="quests-3",
            title="Три квеста",
            condition={"completed_quests_at_least": 3},
            reward_coins=10,
            is_active=True,
        )

    def _complete_quests(self, count: int):
        for i in range(count):
            quest = Quest.objects.create(code=f"q{i}", title=f"Q{i}")
            UserQuestProgress.objects.create(user=self.user, quest=quest, is_completed=True)

    def test_badge_is_granted_when_condition_met(self):
        self._complete_quests(3)

        awarded = award_badges_for_user(self.user)

        self.assertEqual(len(awarded), 1)
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge=self.badge).exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.coins_balance, 10)

    def test_badge_is_not_granted_below_threshold(self):
        self._complete_quests(2)
        self.assertEqual(award_badges_for_user(self.user), [])

    def test_repeated_run_does_not_grant_twice(self):
        self._complete_quests(3)
        award_badges_for_user(self.user)
        coins_after_first = User.objects.get(pk=self.user.pk).coins_balance

        award_badges_for_user(self.user)

        self.assertEqual(UserBadge.objects.filter(user=self.user).count(), 1)
        self.assertEqual(User.objects.get(pk=self.user.pk).coins_balance, coins_after_first)

    def test_progress_is_counted_once_regardless_of_badge_count(self):
        """COUNT по прогрессу квестов выполнялся внутри цикла по значкам."""
        for i in range(5):
            Badge.objects.create(
                code=f"extra-{i}",
                title=f"Значок {i}",
                condition={"completed_quests_at_least": 99},
                is_active=True,
            )
        self._complete_quests(1)

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            award_badges_for_user(self.user)

        progress_counts = [
            q for q in ctx.captured_queries if "quests_userquestprogress" in q["sql"] and "COUNT" in q["sql"].upper()
        ]
        self.assertEqual(len(progress_counts), 1)

    def test_unknown_condition_key_does_not_grant(self):
        Badge.objects.create(
            code="typo",
            title="Опечатка в правиле",
            condition={"completed_quest_at_least": 1},
            is_active=True,
        )
        self._complete_quests(5)

        awarded = award_badges_for_user(self.user)

        self.assertEqual([b.badge.code for b in awarded], ["quests-3"])


class WeeklyTaskTests(TestCase):
    def test_task_walks_activated_agents(self):
        """Задача стояла в расписании с пустым телом: значки не выдавались."""
        user = User.objects.create_user(
            username="agent",
            email="agent@nalchik.ithub.ru",
            password="x",
            callsign="agent_call",
            role=Role.AGENT,
        )
        TelegramAccountLink.objects.create(
            user=user, telegram_user_id=4242, telegram_chat_id=4242, is_active=True
        )
        Badge.objects.create(
            code="starter",
            title="Старт",
            condition={"completed_quests_at_least": 0},
            is_active=True,
        )

        result = check_badges_weekly()

        self.assertIn("checked=1", result)
        self.assertTrue(UserBadge.objects.filter(user=user).exists())

    def test_users_without_telegram_are_skipped(self):
        User.objects.create_user(
            username="ghost", email="g@test.ru", password="x", callsign="ghost_call", role=Role.AGENT
        )
        result = check_badges_weekly()
        self.assertIn("checked=0", result)
