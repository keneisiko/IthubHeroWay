"""Кого платформа считает при начислениях.

Начисления шли только тем, у кого активна привязка Telegram. В закрытом
прогоне студенты в платформу не заходят, привязок нет — и ночные задачи
каждый раз насчитывали ноль, то есть проверяли сами себя.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.models import Role
from apps.integrations.models import TelegramAccountLink
from apps.integrations.services.account_gate import agents_for_scoring

User = get_user_model()


def make_agent(username: str, *, linked: bool, link_active: bool = True) -> User:
    user = User.objects.create_user(
        username=username,
        email=f"{username}@test.ru",
        password="x",
        callsign=f"call_{username}",
        role=Role.AGENT,
        lxp_user_id=f"lxp-{username}",
    )
    if linked:
        telegram_id = abs(hash(username)) % 10**9
        TelegramAccountLink.objects.create(
            user=user,
            telegram_user_id=telegram_id,
            telegram_chat_id=telegram_id,
            is_active=link_active,
        )
    return user


class ScoringAudienceTests(TestCase):
    def setUp(self):
        self.linked = make_agent("linked", linked=True)
        self.unlinked = make_agent("unlinked", linked=False)
        self.disabled_link = make_agent("disabled", linked=True, link_active=False)

    @override_settings(REQUIRE_TELEGRAM_LINK_FOR_SCORING=True)
    def test_boevoy_rezhim_schitaet_tolko_privyazannyh(self):
        self.assertEqual([u.username for u in agents_for_scoring()], ["linked"])

    @override_settings(REQUIRE_TELEGRAM_LINK_FOR_SCORING=False)
    def test_zakrytyy_progon_schitaet_vseh(self):
        usernames = sorted(u.username for u in agents_for_scoring())

        self.assertEqual(usernames, ["disabled", "linked", "unlinked"])

    @override_settings(REQUIRE_TELEGRAM_LINK_FOR_SCORING=True)
    def test_otklyuchennaya_privyazka_ne_schitaetsya(self):
        """Отвязавшийся студент выпадает из начислений, как и не привязавшийся."""
        self.assertNotIn(self.disabled_link, list(agents_for_scoring()))

    @override_settings(REQUIRE_TELEGRAM_LINK_FOR_SCORING=False)
    def test_vhod_ostayotsya_zakrytym(self):
        """Снятие требования привязки не открывает вход импортированным."""
        closed = User.objects.create_user(
            username="imported", email="i@test.ru", password="x", callsign="imp", is_active=False
        )

        self.assertIn(closed.username, [u.username for u in agents_for_scoring()])
        closed.refresh_from_db()
        self.assertFalse(closed.is_active)

    def test_po_umolchaniyu_trebuetsya_privyazka(self):
        """Забытая настройка не должна молча раздавать рейтинг всем подряд."""
        from django.conf import settings

        self.assertTrue(getattr(settings, "REQUIRE_TELEGRAM_LINK_FOR_SCORING", True))
