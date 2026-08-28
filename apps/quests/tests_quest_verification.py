from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.integrations.models import ExternalEvent, TelegramAccountLink
from apps.quests.models import Quest, QuestType, QuestVerifierKind, UserQuestProgress
from apps.quests.services.quest_verification import verify_quest_for_user
from apps.quests.services.verifiers import verify_hik_no_late, verify_hik_on_time

User = get_user_model()


class QuestVerifierTests(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username="agent_v", password="x", callsign="agent_v", role=Role.AGENT
        )
        TelegramAccountLink.objects.create(
            user=self.agent,
            telegram_user_id=8_000_000_001,
            telegram_chat_id=8_000_000_001,
            is_active=True,
        )

    def test_hik_on_time_completes_with_access_event(self):
        today = timezone.localdate()
        ExternalEvent.objects.create(
            source="hik",
            external_event_id="hik-1",
            payload={
                "user_id": self.agent.pk,
                "event_type": "access",
                "late_minutes": 0,
                "event_time": timezone.make_aware(
                    datetime.combine(today, time(9, 30))
                ).isoformat(),
            },
        )
        result = verify_hik_on_time(self.agent, {"deadline_hour": 10}, today)
        self.assertTrue(result.completed)

    def test_hik_no_late_fails_on_late_event(self):
        today = timezone.localdate()
        ExternalEvent.objects.create(
            source="hik",
            external_event_id="hik-late-1",
            payload={
                "user_id": self.agent.pk,
                "event_type": "late",
                "late_minutes": 12,
                "event_time": timezone.now().isoformat(),
            },
        )
        result = verify_hik_no_late(self.agent, {"days": 1}, today)
        self.assertFalse(result.completed)


class QuestAutoCompleteApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.agent = User.objects.create_user(username="agent_api", password="x", callsign="agent_api", role=Role.AGENT)
        self.client.force_authenticate(self.agent)
        self.quest = Quest.objects.create(
            code="daily-auto",
            title="Auto",
            quest_type=QuestType.DAILY,
            is_active=True,
            reward_coins=5,
            reward_rating_delta=2,
            conditions={
                "verifier": QuestVerifierKind.HIK_ON_TIME,
                "params": {"deadline_hour": 10},
                "auto_verify": True,
                "manual_complete_allowed": False,
            },
        )

    def test_manual_complete_blocked_for_auto_quest(self):
        url = reverse("quests-complete", kwargs={"code": self.quest.code})
        response = self.client.post(url, {"proof_payload": {"link": "http://x"}}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_auto_verify_completes_quest(self):
        today = timezone.localdate()
        ExternalEvent.objects.create(
            source="hik",
            external_event_id="hik-auto-1",
            payload={
                "user_id": self.agent.pk,
                "event_type": "access",
                "late_minutes": 0,
                "event_time": timezone.make_aware(datetime.combine(today, time(9, 0))).isoformat(),
            },
        )
        TelegramAccountLink.objects.create(
            user=self.agent,
            telegram_user_id=8_000_000_002,
            telegram_chat_id=8_000_000_002,
            is_active=True,
        )
        outcome = verify_quest_for_user(self.agent, self.quest, today)
        self.assertTrue(outcome.get("completed"))
        self.assertTrue(
            UserQuestProgress.objects.filter(user=self.agent, quest=self.quest, is_completed=True).exists()
        )
