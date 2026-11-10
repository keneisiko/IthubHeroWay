from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
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
                refresh = str(RefreshToken.for_user(self.user))
                response = self.client.post(reverse(name), {"refresh": refresh}, format="json")
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
                refresh = str(RefreshToken.for_user(self.user))
                response = self.client.post(reverse(name), {"refresh": refresh}, format="json")
                self.assertEqual(response.status_code, 200)
                self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
                self.assertEqual(self.client.get(reverse("profile-me")).status_code, 200)
                self.client.credentials()

    def test_rotation_revokes_previous_refresh_on_both_routes(self):
        response = self.client.post(reverse("auth-refresh"), {"refresh": self.refresh}, format="json")
        self.assertEqual(response.status_code, 200)
        rotated = response.json()["refresh"]
        self.assertNotEqual(rotated, self.refresh)

        response = self.client.post(reverse("jwt-refresh"), {"refresh": self.refresh}, format="json")
        self.assertEqual(response.status_code, 401)
        response = self.client.post(reverse("jwt-refresh"), {"refresh": rotated}, format="json")
        self.assertEqual(response.status_code, 200)


class BlockedAdminSessionTests(TestCase):
    def setUp(self):
        self.password = "admin-test-password"
        self.user = User.objects.create_user(
            username="blocked-staff",
            password=self.password,
            role="admin",
            is_staff=True,
            is_active=True,
        )

    def test_password_login_rejects_blocked_staff(self):
        User.objects.filter(pk=self.user.pk).update(login_blocked=True)
        self.assertFalse(self.client.login(username=self.user.username, password=self.password))

    def test_blocking_staff_revokes_existing_admin_session(self):
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        admin_url = reverse("admin:index")
        self.assertEqual(self.client.get(admin_url).status_code, 200)

        User.objects.filter(pk=self.user.pk).update(login_blocked=True)
        self.assertRedirects(
            self.client.get(admin_url),
            f"{reverse('admin:login')}?next={admin_url}",
            fetch_redirect_response=False,
        )
