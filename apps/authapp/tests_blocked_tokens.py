from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class BlockedAccountTokenTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="token-student",
            callsign="token-student",
            password=None,
            role="agent",
            is_active=True,
            login_blocked=False,
        )
        refresh = RefreshToken.for_user(self.user)
        self.refresh = str(refresh)
        self.access = str(refresh.access_token)

    def set_account_state(self, **values):
        User.objects.filter(pk=self.user.pk).update(**values)

    def authenticate_with_access(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def test_old_access_is_rejected_after_login_blocked_only(self):
        self.set_account_state(login_blocked=True)
        self.authenticate_with_access()

        for name in ("auth-me", "profile-me", "dashboard"):
            with self.subTest(endpoint=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 401)

    def test_both_refresh_routes_reject_a_blocked_active_user(self):
        self.set_account_state(login_blocked=True)

        for name in ("auth-refresh", "jwt-refresh"):
            with self.subTest(endpoint=name):
                response = self.client.post(reverse(name), {"refresh": self.refresh}, format="json")
                self.assertEqual(response.status_code, 401)
                self.assertNotIn("access", response.json())

    def test_active_unblocked_user_keeps_access_and_both_refresh_routes(self):
        self.authenticate_with_access()
        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 200)
        self.client.credentials()

        for name in ("auth-refresh", "jwt-refresh"):
            with self.subTest(endpoint=name):
                response = self.client.post(reverse(name), {"refresh": self.refresh}, format="json")
                self.assertEqual(response.status_code, 200)
                self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
                self.assertEqual(self.client.get(reverse("profile-me")).status_code, 200)
                self.client.credentials()

    def test_inactive_user_still_cannot_use_access_or_refresh(self):
        self.set_account_state(is_active=False)
        self.authenticate_with_access()
        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 401)
        self.client.credentials()

        for name in ("auth-refresh", "jwt-refresh"):
            with self.subTest(endpoint=name):
                response = self.client.post(reverse(name), {"refresh": self.refresh}, format="json")
                self.assertEqual(response.status_code, 401)

    def test_unblocking_restores_access_and_both_refresh_routes(self):
        self.set_account_state(login_blocked=True)
        self.authenticate_with_access()
        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 401)
        self.client.credentials()
        for name in ("auth-refresh", "jwt-refresh"):
            with self.subTest(blocked_endpoint=name):
                response = self.client.post(reverse(name), {"refresh": self.refresh}, format="json")
                self.assertEqual(response.status_code, 401)

        self.set_account_state(login_blocked=False)
        self.authenticate_with_access()
        self.assertEqual(self.client.get(reverse("profile-me")).status_code, 200)
        self.client.credentials()
        for name in ("auth-refresh", "jwt-refresh"):
            with self.subTest(unblocked_endpoint=name):
                response = self.client.post(reverse(name), {"refresh": self.refresh}, format="json")
                self.assertEqual(response.status_code, 200)
                self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
                self.assertEqual(self.client.get(reverse("profile-me")).status_code, 200)
                self.client.credentials()
