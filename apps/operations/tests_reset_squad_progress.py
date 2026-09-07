"""Сброс прогресса отряда перед чистым прогоном."""

from __future__ import annotations

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.models import Role, Squad, User
from apps.progress.models import LXPTopicState, RatingLog
from apps.quests.models import Quest, QuestType, UserQuestProgress


class ResetSquadProgressTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="itr2-24", name="3ИТР2.9.24", course=3)
        self.other = Squad.objects.create(code="other", name="Другие", course=1)
        self.agent = self._agent("agent", self.squad, rating=328, coins=40)
        self.outsider = self._agent("outsider", self.other, rating=500, coins=90)

        quest = Quest.objects.create(code="q", title="q", quest_type=QuestType.WEEKLY)
        UserQuestProgress.objects.create(user=self.agent, quest=quest, is_completed=True)
        RatingLog.objects.create(
            user=self.agent, delta=28, value_before=300, value_after=328, reason="Закрыто КТ: 191/1"
        )
        LXPTopicState.objects.create(user=self.agent, topics={"d:1": {"closed": True}})

    def _agent(self, username, squad, rating, coins):
        return User.objects.create_user(
            username=username,
            email=f"{username}@test.ru",
            password="x",
            callsign=f"call_{username}",
            role=Role.AGENT,
            squad=squad,
            rating_current=rating,
            coins_balance=coins,
        )

    def test_false_accruals_are_removed(self):
        call_command("reset_squad_progress", "itr2-24")

        self.agent.refresh_from_db()
        self.assertEqual(self.agent.rating_current, 300)
        self.assertEqual(self.agent.coins_balance, 0)
        self.assertFalse(RatingLog.objects.filter(user=self.agent).exists())
        self.assertFalse(UserQuestProgress.objects.filter(user=self.agent).exists())

    def test_other_squads_are_untouched(self):
        call_command("reset_squad_progress", "itr2-24")

        self.outsider.refresh_from_db()
        self.assertEqual(self.outsider.rating_current, 500)
        self.assertEqual(self.outsider.coins_balance, 90)

    def test_topic_baseline_is_dropped_by_default(self):
        call_command("reset_squad_progress", "itr2-24")

        self.assertFalse(LXPTopicState.objects.filter(user=self.agent).exists())

    def test_topic_baseline_can_be_kept(self):
        call_command("reset_squad_progress", "itr2-24", keep_baseline=True)

        self.assertTrue(LXPTopicState.objects.filter(user=self.agent).exists())

    def test_dry_run_changes_nothing(self):
        call_command("reset_squad_progress", "itr2-24", dry_run=True)

        self.agent.refresh_from_db()
        self.assertEqual(self.agent.rating_current, 328)
        self.assertTrue(RatingLog.objects.filter(user=self.agent).exists())

    def test_unknown_squad_is_refused(self):
        with self.assertRaises(CommandError):
            call_command("reset_squad_progress", "nope")
