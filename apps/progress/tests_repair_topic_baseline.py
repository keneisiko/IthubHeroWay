"""Починка потерянных меток первого снимка.

Метка терялась при каждом новом снимке, и темы прошлых курсов снова
засчитывались недельным квестом — «191/1». Код исправлен, но записи в базе
остались без метки, поэтому нужна разовая починка.
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Squad
from apps.progress.models import LXPTopicState
from apps.quests.services.verifiers import _count_ct_closed_since

User = get_user_model()


class RepairTopicBaselineTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="itr2-24", name="3ИТР2.9.24", course=3)
        self.user = User.objects.create_user(
            username="agent",
            email="a@test.ru",
            password="x",
            callsign="Агент",
            squad=self.squad,
            lxp_user_id="u1",
        )

    def make_state(self, topics: dict) -> LXPTopicState:
        return LXPTopicState.objects.create(
            user=self.user, topics=topics, baseline_done=True, last_snapshot_date=date(2026, 9, 28)
        )

    def test_closed_topics_stop_counting_for_the_week(self):
        self.make_state(
            {f"d:{i}": {"closed": True, "since": "2026-09-25"} for i in range(191)}
        )
        self.assertEqual(_count_ct_closed_since(self.user, date(2026, 9, 21)), 191)

        call_command("repair_topic_baseline", squad="itr2-24")

        self.assertEqual(_count_ct_closed_since(self.user, date(2026, 9, 21)), 0)

    def test_open_topics_are_left_alone(self):
        """Открытую тему помечать нельзя: её сдача — будущее достижение."""
        state = self.make_state({"d:1": {"closed": False, "since": "2026-09-25"}})

        call_command("repair_topic_baseline", squad="itr2-24")

        state.refresh_from_db()
        self.assertNotIn("baseline", state.topics["d:1"])

    def test_dry_run_changes_nothing(self):
        state = self.make_state({"d:1": {"closed": True, "since": "2026-09-25"}})

        call_command("repair_topic_baseline", squad="itr2-24", dry_run=True)

        state.refresh_from_db()
        self.assertNotIn("baseline", state.topics["d:1"])

    def test_repeat_run_is_harmless(self):
        self.make_state({"d:1": {"closed": True, "since": "2026-09-25"}})

        call_command("repair_topic_baseline", squad="itr2-24")
        call_command("repair_topic_baseline", squad="itr2-24")

        self.assertEqual(_count_ct_closed_since(self.user, date(2026, 9, 21)), 0)
