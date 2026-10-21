from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Role, Squad
from apps.quests.admin import SelfReportProofAdmin
from apps.quests.models import (
    Quest,
    QuestRewardTransaction,
    QuestType,
    SelfReportProof,
    SelfReportProofStatus,
    UserQuestProgress,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class SelfReportAdminReviewPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        squad = Squad.objects.create(code="review-own", name="Own squad", course=1)
        other_squad = Squad.objects.create(code="review-other", name="Other squad", course=1)
        users = get_user_model().objects
        cls.curator = users.create_user(
            username="review-curator", callsign="review-curator", role=Role.CURATOR,
            is_staff=True, squad=squad,
        )
        cls.staff_agent = users.create_user(
            username="review-staff", callsign="review-staff", role=Role.AGENT, is_staff=True,
        )
        cls.student = users.create_user(
            username="review-student", callsign="review-student", squad=squad,
            coins_balance=12, rating_current=17,
        )
        other_student = users.create_user(
            username="review-other-student", callsign="review-other-student", squad=other_squad,
            coins_balance=12, rating_current=17,
        )
        cls.quest = Quest.objects.create(
            code="review-permission", title="Review permission quest",
            quest_type=QuestType.SELF_REPORT, reward_coins=5,
        )
        cls.proof = SelfReportProof.objects.create(
            user=cls.student, quest=cls.quest, comment="Completed the assignment",
            quest_progress=UserQuestProgress.objects.create(user=cls.student, quest=cls.quest),
        )
        cls.other_proof = SelfReportProof.objects.create(
            user=other_student, quest=cls.quest, comment="Completed another assignment",
            quest_progress=UserQuestProgress.objects.create(user=other_student, quest=cls.quest),
        )

    def setUp(self):
        self.url = reverse("admin:quests_selfreportproof_changelist")
        self.client.force_login(self.curator)

    def assert_pending_and_unrewarded(self, proof):
        proof.refresh_from_db()
        progress = proof.quest_progress
        progress.refresh_from_db()
        student = proof.user
        student.refresh_from_db()
        self.assertEqual(proof.status, SelfReportProofStatus.PENDING)
        self.assertIsNone(proof.reviewed_by_id)
        self.assertIsNone(proof.reviewed_at)
        self.assertFalse(progress.is_completed)
        self.assertEqual(progress.progress_value, 0)
        self.assertIsNone(progress.completed_at)
        self.assertEqual(student.coins_balance, 12)
        self.assertEqual(student.rating_current, 17)
        self.assertFalse(QuestRewardTransaction.objects.filter(user=student, quest=self.quest).exists())

    def test_staff_without_review_rights_cannot_post_row_decisions(self):
        self.client.force_login(self.staff_agent)

        for field in ("row_approve", "row_reject"):
            with self.subTest(field=field):
                response = self.client.post(self.url, {field: str(self.proof.pk)})

                self.assertEqual(response.status_code, 403)
                self.assert_pending_and_unrewarded(self.proof)

    def test_read_only_curator_cannot_post_row_decisions(self):
        with patch.object(SelfReportProofAdmin, "has_change_permission", return_value=False):
            for field in ("row_approve", "row_reject"):
                with self.subTest(field=field):
                    response = self.client.post(self.url, {field: str(self.proof.pk)})

                    self.assertEqual(response.status_code, 403)
                    self.assert_pending_and_unrewarded(self.proof)

    def test_object_change_permission_is_required_for_row_decisions(self):
        with patch.object(
            SelfReportProofAdmin, "has_change_permission", side_effect=lambda request, obj=None: obj is None,
        ):
            for field in ("row_approve", "row_reject"):
                with self.subTest(field=field):
                    response = self.client.post(self.url, {field: str(self.proof.pk)})

                    self.assertEqual(response.status_code, 403)
                    self.assert_pending_and_unrewarded(self.proof)

    def test_curator_cannot_review_another_squad(self):
        for field in ("row_approve", "row_reject"):
            with self.subTest(field=field):
                response = self.client.post(self.url, {field: str(self.other_proof.pk)})

                self.assertEqual(response.status_code, 403)
                self.assert_pending_and_unrewarded(self.other_proof)

    def test_read_only_list_hides_row_decision_buttons(self):
        with patch.object(SelfReportProofAdmin, "has_change_permission", return_value=False):
            response = self.client.get(self.url)

        self.assertContains(response, "Completed the assignment")
        self.assertNotContains(response, 'name="row_approve"')
        self.assertNotContains(response, 'name="row_reject"')

    def test_object_change_permission_hides_row_decision_buttons(self):
        with patch.object(
            SelfReportProofAdmin, "has_change_permission", side_effect=lambda request, obj=None: obj is None,
        ):
            response = self.client.get(self.url)

        self.assertContains(response, "Completed the assignment")
        self.assertNotContains(response, 'name="row_approve"')
        self.assertNotContains(response, 'name="row_reject"')

    def test_reviewer_list_shows_row_decision_buttons(self):
        response = self.client.get(self.url)

        self.assertContains(response, f'name="row_approve" value="{self.proof.pk}"')
        self.assertContains(response, f'name="row_reject" value="{self.proof.pk}"')

    def test_curator_can_approve_own_squad_proof_once(self):
        for _ in range(2):
            response = self.client.post(self.url, {"row_approve": str(self.proof.pk)})
            self.assertRedirects(response, self.url, fetch_redirect_response=False)

        self.proof.refresh_from_db()
        self.proof.quest_progress.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(self.proof.status, SelfReportProofStatus.APPROVED)
        self.assertEqual(self.proof.reviewed_by, self.curator)
        self.assertIsNotNone(self.proof.reviewed_at)
        self.assertTrue(self.proof.quest_progress.is_completed)
        self.assertEqual(self.student.coins_balance, 17)
        self.assertEqual(self.student.rating_current, 17)
        reward = QuestRewardTransaction.objects.get(user=self.student, quest=self.quest)
        self.assertEqual(reward.coins_delta, 5)

    def test_curator_can_reject_own_squad_proof_without_reward(self):
        response = self.client.post(self.url, {"row_reject": str(self.proof.pk)})

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.proof.refresh_from_db()
        self.proof.quest_progress.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(self.proof.status, SelfReportProofStatus.REJECTED)
        self.assertEqual(self.proof.reviewed_by, self.curator)
        self.assertIsNotNone(self.proof.reviewed_at)
        self.assertFalse(self.proof.quest_progress.is_completed)
        self.assertEqual(self.student.coins_balance, 12)
        self.assertEqual(self.student.rating_current, 17)
        self.assertFalse(QuestRewardTransaction.objects.exists())
