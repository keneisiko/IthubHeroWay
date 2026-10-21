from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PolicyAcceptance, Role
from apps.integrations.models import TelegramAccountLink
from apps.integrations.services.telegram_activation import activate_telegram_account

User = get_user_model()


class InactiveAccountActivationGateTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="inactive_student",
            callsign="inactive_student",
            email="inactive@nalchik.ithub.ru",
            password=None,
            role=Role.AGENT,
            is_active=False,
            status="imported_lxp",
            lxp_user_id="inactive-lxp-id",
        )

    def login(self):
        return self.client.post(
            reverse("auth-login"),
            {"login": self.user.email, "password": "valid-lxp-password"},
            content_type="application/json",
        )

    def activate_in_telegram(self):
        return activate_telegram_account(
            email=self.user.email,
            telegram_user_id=901,
            telegram_chat_id=901,
            telegram_username="inactive_student",
        )

    def assert_inactive_account_stays_closed(self):
        with patch(
            "apps.authapp.serializers.verify_lxp_credentials", return_value=(True, "")
        ):
            response = self.login()
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access", response.json())
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

        links_before = list(TelegramAccountLink.objects.values())
        activated, _ = self.activate_in_telegram()
        self.assertFalse(activated)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(list(TelegramAccountLink.objects.values()), links_before)

    def test_previously_activated_accounts_cannot_reactivate_with_lxp_password(self):
        for account_status in ("activated_web", "activated_telegram", "disabled", ""):
            with self.subTest(status=account_status):
                self.user.status = account_status
                self.user.save(update_fields=["status"])
                self.assert_inactive_account_stays_closed()

    def test_telegram_does_not_reactivate_a_previously_activated_account(self):
        self.user.status = "activated_web"
        self.user.save(update_fields=["status"])

        activated, _ = self.activate_in_telegram()

        self.assertFalse(activated)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(TelegramAccountLink.objects.filter(user=self.user).exists())

    def test_inactive_staff_cannot_reactivate_as_a_student(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.assert_inactive_account_stays_closed()

    def test_inactive_superuser_cannot_reactivate_as_a_student(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self.assert_inactive_account_stays_closed()

    def test_inactive_non_agent_cannot_reactivate_as_a_student(self):
        self.user.role = Role.CURATOR
        self.user.save(update_fields=["role"])
        self.assert_inactive_account_stays_closed()

    def test_import_without_lxp_id_cannot_activate(self):
        for lxp_user_id in (None, "", "   "):
            with self.subTest(lxp_user_id=lxp_user_id):
                self.user.lxp_user_id = lxp_user_id
                self.user.save(update_fields=["lxp_user_id"])
                self.assert_inactive_account_stays_closed()

    def test_import_with_local_password_cannot_reactivate(self):
        self.user.set_password("former-local-password")
        self.user.save(update_fields=["password"])
        self.assert_inactive_account_stays_closed()

    def test_import_with_previous_login_cannot_reactivate(self):
        self.user.last_login = timezone.now()
        self.user.save(update_fields=["last_login"])
        self.assert_inactive_account_stays_closed()

    def test_import_with_telegram_history_cannot_reactivate(self):
        for link_active in (False, True):
            with self.subTest(link_active=link_active):
                TelegramAccountLink.objects.update_or_create(
                    user=self.user,
                    defaults={
                        "telegram_user_id": 902,
                        "telegram_chat_id": 902,
                        "is_active": link_active,
                    },
                )
                self.assert_inactive_account_stays_closed()

    def test_import_with_accepted_policy_cannot_reactivate(self):
        PolicyAcceptance.objects.create(user=self.user, version="1")
        self.assert_inactive_account_stays_closed()

    @patch("apps.authapp.serializers.verify_lxp_credentials", return_value=(True, ""))
    def test_unused_import_can_activate_on_web(self, _verify):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.status, "activated_web")

    def test_unused_import_can_activate_in_telegram(self):
        activated, _ = self.activate_in_telegram()
        self.assertTrue(activated)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.status, "activated_telegram")

    @patch("apps.authapp.serializers.verify_lxp_credentials", return_value=(True, ""))
    def test_active_account_can_log_in_and_link_telegram(self, _verify):
        self.user.is_active = True
        self.user.status = "veteran"
        self.user.save(update_fields=["is_active", "status"])
        response = self.login()
        self.assertEqual(response.status_code, 200)
        activated, _ = self.activate_in_telegram()
        self.assertTrue(activated)
        self.user.refresh_from_db()
        self.assertEqual(self.user.status, "veteran")

    def test_explicit_staff_block_stays_closed_even_for_an_unused_import(self):
        self.user.login_blocked = True
        self.user.save(update_fields=["login_blocked"])
        self.assert_inactive_account_stays_closed()
