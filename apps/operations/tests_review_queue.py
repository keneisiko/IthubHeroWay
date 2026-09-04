"""Очередь подтверждений: кто сколько видит.

Счётчик на главной странице админки и список в разделе проверок обязаны
показывать одно и то же — иначе куратор видит «3 ждут проверки», открывает
список и находит там другое число.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Role, Squad
from apps.operations.services.review_queue import (
    pending_proofs,
    pending_proofs_count,
    reviewable_proofs,
)
from apps.operations.templatetags.review_queue import pending_proofs_for
from apps.quests.models import (
    Quest,
    QuestType,
    SelfReportProof,
    SelfReportProofStatus,
    UserQuestProgress,
)

User = get_user_model()


def make_user(username: str, *, role: str = Role.AGENT, squad=None, staff: bool = False) -> User:
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.ru",
        password="x",
        callsign=f"call_{username}",
        role=role,
        squad=squad,
        is_staff=staff,
    )


def make_proof(student: User, code: str, status: str = SelfReportProofStatus.PENDING) -> SelfReportProof:
    quest = Quest.objects.create(code=code, title=code, quest_type=QuestType.LONG)
    progress = UserQuestProgress.objects.create(user=student, quest=quest)
    return SelfReportProof.objects.create(
        quest=quest, user=student, quest_progress=progress, comment=".", status=status
    )


class ReviewQueueScopeTests(TestCase):
    def setUp(self):
        self.first_course = Squad.objects.create(code="s1", name="Первый", course=1)
        self.third_course = Squad.objects.create(code="s3", name="Третий", course=3)

        self.mine = make_user("mine", squad=self.first_course)
        self.senior = make_user("senior", squad=self.third_course)

        make_proof(self.mine, "q-mine")
        make_proof(self.senior, "q-senior")

        self.curator = make_user("curator", role=Role.CURATOR, squad=self.first_course, staff=True)
        self.tutor = make_user("tutor", role=Role.TUTOR, staff=True)
        self.hq = make_user("hq", role=Role.HQ, staff=True)
        self.admin = make_user("admin", role=Role.ADMIN, staff=True)

    def test_curator_sees_only_own_squad(self):
        self.assertEqual(pending_proofs_count(self.curator), 1)
        self.assertEqual(pending_proofs(self.curator).first().user, self.mine)

    def test_curator_without_squad_sees_nothing(self):
        homeless = make_user("homeless_curator", role=Role.CURATOR, staff=True)

        self.assertEqual(pending_proofs_count(homeless), 0)

    def test_tutor_sees_courses_two_to_four(self):
        self.assertEqual(pending_proofs_count(self.tutor), 1)
        self.assertEqual(pending_proofs(self.tutor).first().user, self.senior)

    def test_hq_reviews_nothing(self):
        """Штаб к проверке подтверждений не допущен."""
        self.assertEqual(pending_proofs_count(self.hq), 0)

    def test_admin_sees_everything(self):
        self.assertEqual(pending_proofs_count(self.admin), 2)

    def test_reviewed_requests_leave_the_queue(self):
        make_proof(self.mine, "q-done", status=SelfReportProofStatus.APPROVED)

        self.assertEqual(pending_proofs_count(self.curator), 1)
        self.assertEqual(reviewable_proofs(self.curator).count(), 2)

    def test_template_tag_matches_the_service(self):
        self.assertEqual(pending_proofs_for(self.curator), pending_proofs_count(self.curator))

    def test_template_tag_is_safe_for_anonymous(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(pending_proofs_for(AnonymousUser()), 0)
