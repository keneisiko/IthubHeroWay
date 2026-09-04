"""Поиск студентов для социальных действий.

Подшефного и соперника вводили по username вручную и точно: опечатка давала
«не удалось оформить» без подсказки, кого вообще можно выбрать.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, Squad
from apps.integrations.models import TelegramAccountLink

User = get_user_model()


def make_agent(
    username: str,
    *,
    callsign: str = "",
    squad=None,
    role: str = Role.AGENT,
    linked: bool = True,
    first_name: str = "",
    last_name: str = "",
) -> User:
    user = User.objects.create_user(
        username=username,
        email=f"{username}@test.ru",
        password="x",
        callsign=callsign or f"call_{username}",
        role=role,
        squad=squad,
        first_name=first_name,
        last_name=last_name,
    )
    if linked:
        TelegramAccountLink.objects.create(
            user=user,
            telegram_user_id=800_000 + user.pk,
            telegram_chat_id=800_000 + user.pk,
            is_active=True,
        )
    return user


class AgentSearchTests(APITestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="alpha", name="Отряд Альфа", course=1)
        self.other_squad = Squad.objects.create(code="beta", name="Отряд Бета", course=2)
        self.me = make_agent("me", callsign="Я", squad=self.squad)
        self.mate = make_agent("mate", callsign="Барс", squad=self.squad, last_name="Иванов")
        self.stranger = make_agent("stranger", callsign="Ветер", squad=self.other_squad)
        self.client.force_authenticate(self.me)
        self.url = reverse("agents-search")

    def _usernames(self, response) -> set[str]:
        return {row["username"] for row in response.json()}

    def test_empty_query_returns_squadmates(self):
        """Чаще всего в подшефные берут своих — их и показываем по умолчанию."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._usernames(response), {"mate"})

    def test_search_finds_by_callsign(self):
        response = self.client.get(self.url, {"q": "Вет"})

        self.assertEqual(self._usernames(response), {"stranger"})

    def test_search_finds_by_last_name(self):
        response = self.client.get(self.url, {"q": "Иван"})

        self.assertEqual(self._usernames(response), {"mate"})

    def test_search_finds_by_username(self):
        response = self.client.get(self.url, {"q": "strang"})

        self.assertEqual(self._usernames(response), {"stranger"})

    def test_self_is_never_suggested(self):
        """Самонаставничество и дуэль с собой запрещены — незачем и предлагать."""
        response = self.client.get(self.url, {"q": "Я"})

        self.assertNotIn("me", self._usernames(response))

    def test_unactivated_accounts_are_hidden(self):
        make_agent("ghost", callsign="Призрак", squad=self.squad, linked=False)

        response = self.client.get(self.url, {"q": "Призрак"})

        self.assertEqual(self._usernames(response), set())

    def test_staff_are_not_agents(self):
        make_agent("curator", callsign="Куратор", squad=self.squad, role=Role.CURATOR)

        response = self.client.get(self.url, {"q": "Куратор"})

        self.assertEqual(self._usernames(response), set())

    def test_row_carries_data_for_the_card(self):
        response = self.client.get(self.url, {"q": "Барс"})

        row = response.json()[0]
        self.assertEqual(row["callsign"], "Барс")
        self.assertEqual(row["squad"], "Отряд Альфа")
        self.assertIn("rating_current", row)

    def test_anonymous_is_rejected(self):
        self.client.force_authenticate(None)

        response = self.client.get(self.url)

        self.assertIn(response.status_code, (401, 403))
