"""Самоотчёт с карточки квеста идёт через /complete/ и привязан к квесту."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.operations.models import PlatformSettings
from apps.operations.services.platform_settings import invalidate
from apps.quests.models import Quest, QuestType, SelfReportProof

User = get_user_model()


class ReportFromCardTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="st", password="x", callsign="st", role=Role.AGENT
        )
        self.client.force_authenticate(self.user)
        self.quest = Quest.objects.create(
            code="self-report-practice", title="Дневник практики", quest_type=QuestType.SELF_REPORT
        )

    def send(self, quest: Quest):
        return self.client.post(
            reverse("quests-complete", args=[quest.code]),
            {"proof_payload": {"comment": "Заполнил дневник за неделю", "link": "https://example.com/d"}},
            format="json",
        )

    def test_self_report_quest_is_reportable_and_proof_is_linked(self):
        active = self.client.get(reverse("quests-active")).json()
        row = next(q for q in active if q["code"] == self.quest.code)
        self.assertTrue(row["manual_complete_allowed"])

        self.assertEqual(self.send(self.quest).status_code, 201)
        proof = SelfReportProof.objects.get()
        self.assertEqual(proof.quest, self.quest)
        self.assertEqual(proof.attachment_link, "https://example.com/d")

    def test_daily_self_report_limit_applies(self):
        PlatformSettings.objects.filter(pk=PlatformSettings.SINGLETON_PK).update(max_daily_self_reports=1)
        invalidate()
        # Настройки кешируются: без сброса после теста их видят соседние тесты.
        self.addCleanup(invalidate)
        other = Quest.objects.create(code="self-report-lab", title="Лаба", quest_type=QuestType.SELF_REPORT)
        self.assertEqual(self.send(self.quest).status_code, 201)
        self.assertEqual(self.send(other).status_code, 429)
