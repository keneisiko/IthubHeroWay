from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Role, Squad
from apps.integrations.models import TelegramAccountLink

User = get_user_model()


class SquadsApiTests(APITestCase):
    def _telegram(self, user):
        TelegramAccountLink.objects.create(
            user=user,
            telegram_user_id=9_000_000_000 + user.pk,
            telegram_chat_id=9_000_000_000 + user.pk,
            is_active=True,
        )

    def setUp(self):
        self.squad = Squad.objects.create(code="alpha-2025", name="Alpha", course=2, capacity=2)
        self.agent = User.objects.create_user(
            username="agent1", password="x", callsign="agent1", role=Role.AGENT
        )
        self.agent2 = User.objects.create_user(
            username="agent2", password="x", callsign="agent2", role=Role.AGENT
        )
        self.member = User.objects.create_user(
            username="member1",
            password="x",
            callsign="member1",
            role=Role.AGENT,
            squad=self.squad,
        )
        self._telegram(self.member)

    def test_squad_me_without_squad_returns_200(self):
        self.client.force_authenticate(self.agent)
        response = self.client.get(reverse("squads-me"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["my_squad"])
        self.assertIn("join", response.data["available_actions"])

    def test_join_squad(self):
        self.client.force_authenticate(self.agent)
        response = self.client.post(reverse("squads-join"), {"code": "alpha-2025"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.squad_id, self.squad.id)

    def test_join_when_already_in_squad_fails(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(reverse("squads-join"), {"code": "alpha-2025"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_create_squad(self):
        self.client.force_authenticate(self.agent2)
        response = self.client.post(
            reverse("squads-list"),
            {"name": "Новый отряд", "course": 1, "capacity": 10},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.agent2.refresh_from_db()
        self.assertIsNotNone(self.agent2.squad_id)

    def test_squad_list(self):
        self.client.force_authenticate(self.agent)
        response = self.client.get(reverse("squads-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.data) >= 1)

    def test_leave_squad(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(reverse("squads-leave"))
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.squad_id)

    def test_join_full_squad_fails(self):
        m2 = User.objects.create_user(
            username="member2", password="x", callsign="member2", role=Role.AGENT, squad=self.squad
        )
        self._telegram(m2)
        self.client.force_authenticate(self.agent)
        response = self.client.post(reverse("squads-join"), {"code": "alpha-2025"}, format="json")
        self.assertEqual(response.status_code, 400)
