"""Активация аккаунта: импорт из LXP не должен открывать вход.

Импорт заводит карточки всем студентам колледжа. Если такая карточка сразу
активна, войти на платформу может любой, у кого есть пароль от LXP, — то есть
все импортированные, независимо от того, знают ли они про бота. Подтверждением
служит привязка Telegram.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.integrations.models import TelegramAccountLink
from apps.integrations.services.account_gate import deactivate_unlinked_agents
from apps.integrations.services.telegram_activation import activate_telegram_account

User = get_user_model()


def _imported_agent(**overrides):
    defaults = {
        "username": "student_1",
        "callsign": "lxp_1",
        "email": "student@nalchik.ithub.ru",
        "role": Role.AGENT,
        "is_active": False,
        "status": "imported_lxp",
        "lxp_user_id": "1",
    }
    defaults.update(overrides)
    user = User.objects.create(**defaults)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user


class TelegramActivationOpensLoginTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_activation_makes_imported_account_active(self):
        user = _imported_agent()

        ok, _ = activate_telegram_account(
            email="student@nalchik.ithub.ru",
            telegram_user_id=101,
            telegram_chat_id=101,
            telegram_username="stud",
        )

        self.assertTrue(ok)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(user.status, "activated_telegram")

    def test_failed_activation_leaves_account_closed(self):
        """Чужой Telegram уже привязан — вход открываться не должен."""
        other = _imported_agent(
            username="other", callsign="lxp_2", email="other@nalchik.ithub.ru", lxp_user_id="2"
        )
        TelegramAccountLink.objects.create(
            user=other, telegram_user_id=202, telegram_chat_id=202, is_active=True
        )
        user = _imported_agent()

        ok, _ = activate_telegram_account(
            email="student@nalchik.ithub.ru",
            telegram_user_id=202,
            telegram_chat_id=202,
            telegram_username="",
        )

        self.assertFalse(ok)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_status_of_non_imported_user_is_not_overwritten(self):
        user = _imported_agent(status="ветеран", is_active=True)

        activate_telegram_account(
            email="student@nalchik.ithub.ru",
            telegram_user_id=303,
            telegram_chat_id=303,
            telegram_username="",
        )

        user.refresh_from_db()
        self.assertEqual(user.status, "ветеран")


class DeactivateUnlinkedAgentsTests(TestCase):
    """Разовая чистка баз, импортированных до фикса."""

    def test_agents_without_link_are_closed(self):
        user = _imported_agent(is_active=True)

        self.assertEqual(deactivate_unlinked_agents(), 1)

        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_linked_agents_are_left_alone(self):
        user = _imported_agent(is_active=True)
        TelegramAccountLink.objects.create(
            user=user, telegram_user_id=404, telegram_chat_id=404, is_active=True
        )

        self.assertEqual(deactivate_unlinked_agents(), 0)

        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_staff_and_non_agents_are_left_alone(self):
        """Кураторы и админы входят не через бота — их отключать нельзя."""
        curator = _imported_agent(
            username="curator", callsign="cur", email="c@nalchik.ithub.ru",
            role=Role.CURATOR, is_active=True, lxp_user_id="3",
        )
        staff = _imported_agent(
            username="staffer", callsign="stf", email="s@nalchik.ithub.ru",
            is_active=True, lxp_user_id="4",
        )
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])

        self.assertEqual(deactivate_unlinked_agents(), 0)

        curator.refresh_from_db()
        staff.refresh_from_db()
        self.assertTrue(curator.is_active)
        self.assertTrue(staff.is_active)


class LoginGateTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("apps.authapp.serializers.verify_lxp_credentials", return_value=(True, ""))
    def test_imported_account_cannot_log_in_before_activation(self, verify):
        _imported_agent()

        response = self.client.post(
            reverse("auth-login"),
            {"login": "student@nalchik.ithub.ru", "password": "lxp-password"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        # До LXP запрос вообще не доходит: аккаунт закрыт.
        verify.assert_not_called()

    @patch("apps.authapp.serializers.verify_lxp_credentials", return_value=(True, ""))
    def test_login_works_after_telegram_activation(self, _verify):
        _imported_agent()
        activate_telegram_account(
            email="student@nalchik.ithub.ru",
            telegram_user_id=505,
            telegram_chat_id=505,
            telegram_username="",
        )

        response = self.client.post(
            reverse("auth-login"),
            {"login": "student@nalchik.ithub.ru", "password": "lxp-password"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
