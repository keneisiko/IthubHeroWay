"""Активация аккаунта: в боте или первым входом на сайт.

Импорт заводит карточки неактивными. Раньше открыть такую карточку можно было
только через /activate в боте — к 21.10.2026 так вошли двое из 557. Бот
проверяет учебную почту и пароль от LXP; вход на сайт проверяет то же самое,
поэтому первый вход с верным паролем тоже активирует аккаунт. Отключённых
сотрудником не открывает ни то, ни другое (`login_blocked`).
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

    def login(self):
        return self.client.post(
            reverse("auth-login"),
            {"login": "student@nalchik.ithub.ru", "password": "lxp-password"},
            content_type="application/json",
        )

    @patch("apps.authapp.serializers.verify_lxp_credentials", return_value=(True, ""))
    def test_first_login_with_lxp_password_activates_account(self, _verify):
        user = _imported_agent()

        response = self.login()

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(user.status, "activated_web")

    @patch("apps.authapp.serializers.verify_lxp_credentials", return_value=(False, "Неверный пароль"))
    def test_wrong_password_does_not_activate(self, _verify):
        user = _imported_agent()

        response = self.login()

        self.assertEqual(response.status_code, 401)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    @patch("apps.authapp.serializers.verify_lxp_credentials", return_value=(True, ""))
    def test_blocked_by_staff_cannot_log_in(self, verify):
        _imported_agent(login_blocked=True)

        response = self.login()

        self.assertEqual(response.status_code, 401)
        self.assertIn("Вход закрыт", response.json()["detail"])
        # До LXP запрос не доходит: решение уже принято сотрудником.
        verify.assert_not_called()

    def test_blocked_by_staff_cannot_activate_in_bot_either(self):
        user = _imported_agent(login_blocked=True)

        ok, _ = activate_telegram_account(
            email="student@nalchik.ithub.ru", telegram_user_id=606, telegram_chat_id=606, telegram_username=""
        )

        self.assertFalse(ok)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

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


class StaffDeactivationTests(TestCase):
    """Снятая сотрудником галочка «Активный» — намеренное отключение."""

    def setUp(self):
        from django.test import override_settings

        self.enterContext(override_settings(SECURE_SSL_REDIRECT=False))
        self.boss = User.objects.create_user(
            username="boss", password="x", callsign="boss", role=Role.ADMIN, is_staff=True
        )
        self.client.force_login(self.boss)
        self.student = _imported_agent(is_active=True, status="")

    def post_active(self, value: bool):
        """Сохранить карточку студента так, как это делает сотрудник в админке."""
        url = reverse("admin:accounts_user_change", args=[self.student.pk])
        initial = self.client.get(url).context["adminform"].form.initial
        data = {
            k: v for k, v in initial.items()
            if v is not None and not isinstance(v, (list, tuple)) and k != "avatar"
        }
        data.update({"role": Role.AGENT})
        if value:
            data["is_active"] = "on"
        else:
            data.pop("is_active", None)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, "форма карточки не сохранилась")

    def test_unchecking_active_blocks_login(self):
        self.post_active(False)

        self.student.refresh_from_db()
        self.assertTrue(self.student.login_blocked)

    def test_checking_active_again_unblocks(self):
        self.post_active(False)
        self.post_active(True)

        self.student.refresh_from_db()
        self.assertFalse(self.student.login_blocked)


class TelegramBadgeOnActivationTests(TestCase):
    """Нашивка «На связи» — в момент привязки, а не на ближайшей проверке.

    Проверка шла раз в неделю: привязавшие Telegram 20.10 ждали бы нашивку
    до воскресенья и считали её сломанной.
    """

    def test_badge_is_awarded_right_after_activate(self):
        from apps.badges.models import Badge, UserBadge

        badge = Badge.objects.create(
            code="telegram-linked", title="На связи", condition={"telegram_linked": True}, reward_coins=5
        )
        user = _imported_agent()

        ok, _ = activate_telegram_account(
            email="student@nalchik.ithub.ru", telegram_user_id=707, telegram_chat_id=707, telegram_username=""
        )

        self.assertTrue(ok)
        self.assertTrue(UserBadge.objects.filter(user=user, badge=badge).exists())
        user.refresh_from_db()
        self.assertEqual(user.coins_balance, 5)
