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
        # Участие в отрядах требует активации в Telegram-боте. Раньше эндпоинт
        # молча создавал привязку сам, поэтому тесты обходились без неё.
        self._telegram(self.agent)
        self._telegram(self.agent2)

    def test_join_without_telegram_is_rejected(self):
        """Гейт «активирован в боте» должен работать, а не обходиться."""
        stranger = User.objects.create_user(
            username="stranger", password="x", callsign="stranger", role=Role.AGENT
        )
        self.client.force_authenticate(stranger)

        response = self.client.post(reverse("squads-join"), {"code": "alpha-2025"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        stranger.refresh_from_db()
        self.assertIsNone(stranger.squad_id)
        self.assertFalse(TelegramAccountLink.objects.filter(user=stranger).exists())

    def test_create_squad_without_telegram_is_rejected(self):
        stranger = User.objects.create_user(
            username="stranger2", password="x", callsign="stranger2", role=Role.AGENT
        )
        self.client.force_authenticate(stranger)

        response = self.client.post(reverse("squads-list"), {"name": "Новый"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(TelegramAccountLink.objects.filter(user=stranger).exists())

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

    def test_squad_never_exceeds_capacity(self):
        """Проверка мест и запись шли вне транзакции: два вступления подряд
        (в проде — параллельно) оба видели свободное место."""
        self.assertEqual(self.squad.capacity, 2)
        codes = []
        for agent in (self.agent, self.agent2):
            self.client.force_authenticate(agent)
            codes.append(
                self.client.post(
                    reverse("squads-join"), {"code": "alpha-2025"}, format="json"
                ).status_code
            )

        joined = User.objects.filter(
            squad=self.squad, role=Role.AGENT, telegram_link__is_active=True
        ).count()
        self.assertEqual(joined, self.squad.capacity)
        self.assertEqual(sorted(codes), [200, 400])

    def test_squads_with_same_name_get_distinct_codes(self):
        """Код подбирался через exists() + create(): при совпадении названий
        второй запрос падал с IntegrityError наружу."""
        payload = {"name": "Отряд", "course": 1, "capacity": 10}
        created_codes = set()
        for agent in (self.agent, self.agent2):
            self.client.force_authenticate(agent)
            response = self.client.post(reverse("squads-list"), payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            created_codes.add(response.data["code"])
        self.assertEqual(len(created_codes), 2)

    def test_members_list_search_and_long_query(self):
        self.client.force_authenticate(self.member)
        url = reverse("squads-members", args=[self.squad.code])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([m["callsign"] for m in response.data], ["member1"])

        self.assertEqual(self.client.get(url, {"search": "member"}).data[0]["callsign"], "member1")
        self.assertEqual(self.client.get(url, {"search": "нет"}).data, [])
        self.assertEqual(self.client.get(url, {"search": "x" * 5000}).status_code, 200)

    def test_join_full_squad_fails(self):
        m2 = User.objects.create_user(
            username="member2", password="x", callsign="member2", role=Role.AGENT, squad=self.squad
        )
        self._telegram(m2)
        self.client.force_authenticate(self.agent)
        response = self.client.post(reverse("squads-join"), {"code": "alpha-2025"}, format="json")
        self.assertEqual(response.status_code, 400)
