"""Ручное подтверждение квеста уходит на проверку куратору.

Раньше `POST /quests/<code>/complete/` закрывал квест сразу и начислял монеты
с рейтингом. Ссылку-доказательство никто не смотрел — она просто писалась
в `proof_payload`. Любой квест с ручным подтверждением был источником
бесплатной награды: нажал, отправил пустое поле, получил рейтинг.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.quests.models import (
    Quest,
    QuestRewardTransaction,
    QuestType,
    QuestVerifierKind,
    SelfReportProof,
    SelfReportProofStatus,
    UserQuestProgress,
)
from apps.quests.services.quest_completion import complete_quest_idempotent

User = get_user_model()


class ManualConfirmationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="confirmer",
            email="confirmer@test.ru",
            password="x",
            callsign="confirmer_call",
            role=Role.AGENT,
            rating_current=300,
            coins_balance=0,
        )
        self.client.force_authenticate(self.user)
        self.manual = Quest.objects.create(
            code="manual-hackathon",
            title="Хакатон",
            quest_type=QuestType.LONG,
            reward_coins=40,
            reward_rating_delta=25,
            conditions={"manual_complete_allowed": True},
            end_at=timezone.now() + timedelta(days=3),
        )
        self.auto = Quest.objects.create(
            code="auto-checkin",
            title="Чек-ин",
            quest_type=QuestType.DAILY,
            reward_coins=5,
            reward_rating_delta=2,
            conditions={"verifier": QuestVerifierKind.HIK_ON_TIME, "auto_verify": True},
        )

    def _url(self, quest: Quest) -> str:
        return reverse("quests-complete", args=[quest.code])

    def test_confirmation_creates_pending_review_without_reward(self):
        response = self.client.post(
            self._url(self.manual),
            {"proof_payload": {"link": "https://github.com/demo/hack"}},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], SelfReportProofStatus.PENDING)

        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, 300, "награда до проверки не начисляется")
        self.assertEqual(self.user.coins_balance, 0)
        self.assertFalse(QuestRewardTransaction.objects.filter(user=self.user).exists())
        self.assertFalse(UserQuestProgress.objects.get(user=self.user, quest=self.manual).is_completed)

    def test_link_is_saved_for_the_curator(self):
        self.client.post(
            self._url(self.manual),
            {"proof_payload": {"link": "https://gitlab.com/demo/work"}},
            format="json",
        )

        proof = SelfReportProof.objects.get(user=self.user, quest=self.manual)
        self.assertEqual(proof.attachment_link, "https://gitlab.com/demo/work")
        self.assertEqual(proof.status, SelfReportProofStatus.PENDING)

    def test_reward_arrives_only_after_approval(self):
        self.client.post(self._url(self.manual), {"proof_payload": {}}, format="json")
        proof = SelfReportProof.objects.get(user=self.user, quest=self.manual)

        proof.status = SelfReportProofStatus.APPROVED
        proof.save(update_fields=["status"])
        complete_quest_idempotent(self.user, self.manual, reason="Квест подтверждён куратором")

        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, 325)
        # Монеты режет дневной лимит MAX_DAILY_COINS — так и задумано:
        # рейтинг за квест приходит целиком, монеты в пределах суточной нормы.
        self.assertEqual(self.user.coins_balance, 20)

    def test_second_submission_updates_the_same_request(self):
        """Студент может переприслать ссылку, а не плодить заявки."""
        self.client.post(
            self._url(self.manual), {"proof_payload": {"link": "https://a.example/1"}}, format="json"
        )
        response = self.client.post(
            self._url(self.manual), {"proof_payload": {"link": "https://b.example/2"}}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SelfReportProof.objects.filter(user=self.user, quest=self.manual).count(), 1)
        proof = SelfReportProof.objects.get(user=self.user, quest=self.manual)
        self.assertEqual(proof.attachment_link, "https://b.example/2")

    def test_rejected_request_can_be_resubmitted(self):
        self.client.post(self._url(self.manual), {"proof_payload": {}}, format="json")
        SelfReportProof.objects.filter(user=self.user).update(
            status=SelfReportProofStatus.REJECTED, reviewed_at=timezone.now()
        )

        self.client.post(
            self._url(self.manual), {"proof_payload": {"link": "https://c.example/3"}}, format="json"
        )

        proof = SelfReportProof.objects.get(user=self.user, quest=self.manual)
        self.assertEqual(proof.status, SelfReportProofStatus.PENDING)
        self.assertIsNone(proof.reviewed_at, "заявка снова ждёт проверки")

    def test_approved_request_is_not_reopened(self):
        self.client.post(self._url(self.manual), {"proof_payload": {}}, format="json")
        SelfReportProof.objects.filter(user=self.user).update(status=SelfReportProofStatus.APPROVED)

        response = self.client.post(self._url(self.manual), {"proof_payload": {}}, format="json")

        self.assertEqual(response.status_code, 400)

    def test_auto_verified_quest_cannot_be_confirmed_by_hand(self):
        response = self.client.post(self._url(self.auto), {"proof_payload": {}}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(SelfReportProof.objects.filter(quest=self.auto).exists())

    def test_expired_quest_is_rejected(self):
        self.manual.end_at = timezone.now() - timedelta(days=1)
        self.manual.save(update_fields=["end_at"])

        response = self.client.post(self._url(self.manual), {"proof_payload": {}}, format="json")

        self.assertEqual(response.status_code, 400)

    def test_progress_exposes_review_status(self):
        """Интерфейс по нему показывает «Отправлено куратору»."""
        self.client.post(self._url(self.manual), {"proof_payload": {}}, format="json")

        response = self.client.get(reverse("quests-my-progress"), {"completed": "false"})

        rows = response.json()["results"]
        row = next(r for r in rows if r["quest"]["code"] == self.manual.code)
        self.assertEqual(row["review_status"], SelfReportProofStatus.PENDING)
