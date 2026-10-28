"""Вчерашние ежедневные квесты засчитываются, когда данные пришли на следующий день."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role
from apps.integrations.models import ExternalEvent
from apps.quests.models import QuestTemplate, QuestType, QuestVerifierKind, UserQuestProgress
from apps.quests.services.quest_periods import period_key_for
from apps.quests.tasks import verify_auto_quests, verify_previous_day_quests

User = get_user_model()


class PreviousDayVerificationTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="st", password="x", callsign="st", role=Role.AGENT
        )
        QuestTemplate.objects.create(
            code="daily-hik-on-time",
            title="Утренний чек-ин",
            quest_type=QuestType.DAILY,
            verifier=QuestVerifierKind.HIK_ON_TIME,
            verifier_params={"deadline_hour": 10},
            is_active=True,
        )
        self.yesterday = timezone.localdate() - timedelta(days=1)

    def pass_yesterday(self):
        """Проход за вчера, пришедший сегодня вечером — как выгрузка Hik."""
        ExternalEvent.objects.create(
            source="hik",
            external_event_id="late-arrival",
            user=self.student,
            event_date=self.yesterday,
            event_type="access",
            payload={
                "event_type": "access",
                "late_minutes": 0,
                "event_time": timezone.make_aware(datetime.combine(self.yesterday, time(8, 50))).isoformat(),
            },
        )

    def yesterday_done(self) -> bool:
        return UserQuestProgress.objects.filter(
            user=self.student,
            quest__code=f"daily-hik-on-time:{period_key_for(QuestType.DAILY, self.yesterday)}",
            is_completed=True,
        ).exists()

    def test_todays_check_misses_data_that_arrives_next_day(self):
        self.pass_yesterday()
        verify_auto_quests()
        self.assertFalse(self.yesterday_done())

    def test_previous_day_check_completes_yesterdays_quest(self):
        self.pass_yesterday()
        verify_previous_day_quests()
        self.assertTrue(self.yesterday_done())
