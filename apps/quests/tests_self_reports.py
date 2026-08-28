from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, Squad, Track
from apps.quests.admin import QuestRewardTransactionAdmin, SelfReportProofAdmin
from apps.quests.models import Quest, QuestType, SelfReportProof, SelfReportProofStatus, UserQuestProgress


class SelfReportApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="agent1", password="x", callsign="agent1")
        self.client.force_authenticate(self.user)
        self.quest = Quest.objects.create(
            code="sr-1",
            title="Self report quest",
            quest_type=QuestType.SELF_REPORT,
            reward_coins=5,
            reward_rating_delta=10,
            is_active=True,
        )

    def test_create_self_report(self):
        url = reverse("quests-self-report", kwargs={"code": self.quest.code})
        response = self.client.post(url, {"comment": "abcdefghij"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "pending")
        self.assertTrue(SelfReportProof.objects.filter(user=self.user, quest=self.quest).exists())

    def test_fourth_self_report_rejected(self):
        for i in range(3):
            quest = Quest.objects.create(
                code=f"sr-limit-{i}",
                title=f"SR {i}",
                quest_type=QuestType.SELF_REPORT,
                is_active=True,
            )
            url = reverse("quests-self-report", kwargs={"code": quest.code})
            response = self.client.post(url, {"comment": "abcdefghij"}, format="json")
            self.assertEqual(response.status_code, 201, msg=f"quest {i}")
            # Сдвиг нужен только чтобы обойти кулдаун в 5 минут между
            # самоотчётами. Сдвигать на час нельзя: дневной лимит считается
            # от местной полуночи, и при прогоне вскоре после неё записи
            # уезжали во вчера, а лимит переставал срабатывать.
            SelfReportProof.objects.filter(user=self.user, quest=quest).update(
                created_at=timezone.now() - timedelta(minutes=6)
            )

        overflow = Quest.objects.create(code="sr-limit-4", title="SR 4", quest_type=QuestType.SELF_REPORT, is_active=True)
        url = reverse("quests-self-report", kwargs={"code": overflow.code})
        response = self.client.post(url, {"comment": "abcdefghij"}, format="json")
        self.assertEqual(response.status_code, 429)


class SelfReportAdminQuerysetTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = SelfReportProofAdmin(SelfReportProof, self.site)

        track = Track.objects.create(code="t", name="Track")
        self.squad1 = Squad.objects.create(code="S1", name="S1", course=1)
        self.squad2 = Squad.objects.create(code="S2", name="S2", course=3)

        self.curator = get_user_model().objects.create_user(
            username="cur", password="x", callsign="cur", role=Role.CURATOR, is_staff=True, squad=self.squad1
        )
        self.tutor = get_user_model().objects.create_user(
            username="tut", password="x", callsign="tut", role=Role.TUTOR, is_staff=True
        )
        self.admin_user = get_user_model().objects.create_user(
            username="adm", password="x", callsign="adm", role=Role.ADMIN, is_staff=True
        )
        self.hq = get_user_model().objects.create_user(
            username="hq", password="x", callsign="hq", role=Role.HQ, is_staff=True
        )

        self.agent1 = get_user_model().objects.create_user(
            username="a1", password="x", callsign="a1", role=Role.AGENT, squad=self.squad1, track=track
        )
        self.agent2 = get_user_model().objects.create_user(
            username="a2", password="x", callsign="a2", role=Role.AGENT, squad=self.squad2, track=track
        )
        self.quest = Quest.objects.create(code="sr-2", title="SR", quest_type=QuestType.SELF_REPORT, is_active=True)
        p1 = UserQuestProgress.objects.create(user=self.agent1, quest=self.quest)
        p2 = UserQuestProgress.objects.create(user=self.agent2, quest=self.quest)
        SelfReportProof.objects.create(
            quest=self.quest, user=self.agent1, quest_progress=p1, comment="abcdefghij", status=SelfReportProofStatus.PENDING
        )
        SelfReportProof.objects.create(
            quest=self.quest, user=self.agent2, quest_progress=p2, comment="abcdefghij", status=SelfReportProofStatus.PENDING
        )

    def test_curator_sees_only_own_squad(self):
        request = self.factory.get("/admin/quests/selfreportproof/")
        request.user = self.curator
        qs = self.admin.get_queryset(request)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().user.squad_id, self.squad1.id)

    def test_tutor_sees_only_course_2_4(self):
        request = self.factory.get("/admin/quests/selfreportproof/")
        request.user = self.tutor
        qs = self.admin.get_queryset(request)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().user.squad_id, self.squad2.id)

    def test_admin_sees_all(self):
        request = self.factory.get("/admin/quests/selfreportproof/")
        request.user = self.admin_user
        qs = self.admin.get_queryset(request)
        self.assertEqual(qs.count(), 2)

    def test_hq_has_no_module_permission(self):
        request = self.factory.get("/admin/quests/selfreportproof/")
        request.user = self.hq
        self.assertFalse(self.admin.has_module_permission(request))


class QuestRewardTransactionAdminTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        from apps.quests.models import QuestRewardTransaction

        self.admin = QuestRewardTransactionAdmin(QuestRewardTransaction, self.site)
        self.hq = get_user_model().objects.create_user(
            username="hq2", password="x", callsign="hq2", role=Role.HQ, is_staff=True
        )

    def test_hq_denied_quest_reward_transaction(self):
        request = self.factory.get("/admin/quests/questrewardtransaction/")
        request.user = self.hq
        self.assertFalse(self.admin.has_module_permission(request))

