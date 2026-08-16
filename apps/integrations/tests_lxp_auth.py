"""Тесты проверки учётных данных через LXP.

Ключевое здесь — запасной путь. Когда настройки LXP пусты, функция может
пустить пользователя по локальному паролю Django. В разработке это удобно,
в продакшене — тихая подмена «входа через LXP» входом по локальному паролю,
о которой пользователю продолжают писать обратное. Тесты фиксируют, что
откат работает только при DEBUG=True.
"""

from unittest.mock import Mock, patch

import requests
from django.test import TestCase, override_settings

from apps.integrations.services.lxp_auth import verify_lxp_credentials
from conftest import make_agent

GRAPHQL_SETTINGS = dict(
    LXP_GRAPHQL_ENDPOINT="https://api.example.test/graphql", LXP_VERIFY_URL=""
)
REST_SETTINGS = dict(LXP_GRAPHQL_ENDPOINT="", LXP_VERIFY_URL="https://lxp.example.test/verify")
NO_LXP_SETTINGS = dict(LXP_GRAPHQL_ENDPOINT="", LXP_VERIFY_URL="")


def _response(*, status_code=200, json_value=None):
    resp = Mock()
    resp.status_code = status_code
    resp.content = b"{}"
    resp.json.return_value = json_value if json_value is not None else {}
    return resp


@override_settings(**GRAPHQL_SETTINGS)
class GraphQLPathTests(TestCase):
    @patch("apps.integrations.services.lxp_auth.requests.post")
    def test_access_token_means_verified(self, post):
        post.return_value = _response(json_value={"data": {"signIn": {"accessToken": "a.b.c"}}})

        ok, message = verify_lxp_credentials("agent@nalchik.ithub.ru", "pwd")

        self.assertTrue(ok)
        self.assertEqual(message, "verified")

    @patch("apps.integrations.services.lxp_auth.requests.post")
    def test_graphql_errors_mean_wrong_credentials(self, post):
        post.return_value = _response(json_value={"errors": [{"message": "Invalid"}]})

        ok, message = verify_lxp_credentials("agent@nalchik.ithub.ru", "pwd")

        self.assertFalse(ok)
        self.assertIn("Invalid LXP", message)

    @patch("apps.integrations.services.lxp_auth.requests.post")
    def test_response_without_token_is_not_a_success(self, post):
        """Пустой signIn раньше можно было принять за успех — вход без пароля."""
        post.return_value = _response(json_value={"data": {"signIn": None}})

        ok, _ = verify_lxp_credentials("agent@nalchik.ithub.ru", "pwd")

        self.assertFalse(ok)

    @patch("apps.integrations.services.lxp_auth.requests.post")
    def test_http_error_is_reported_as_unavailable(self, post):
        post.return_value = _response(status_code=502)

        ok, message = verify_lxp_credentials("agent@nalchik.ithub.ru", "pwd")

        self.assertFalse(ok)
        self.assertIn("unavailable", message)

    @patch("apps.integrations.services.lxp_auth.requests.post")
    def test_network_error_is_reported_as_unavailable(self, post):
        post.side_effect = requests.Timeout("timeout")

        ok, message = verify_lxp_credentials("agent@nalchik.ithub.ru", "pwd")

        self.assertFalse(ok)
        self.assertIn("unavailable", message)

    @override_settings(**NO_LXP_SETTINGS)
    @patch("apps.integrations.services.lxp_auth.requests.post")
    def test_graphql_endpoint_wins_over_local_password(self, post):
        """Проверка идёт в LXP, а не по локальной базе, если endpoint задан."""
        with override_settings(**GRAPHQL_SETTINGS):
            post.return_value = _response(json_value={"data": {"signIn": {"accessToken": "a.b.c"}}})
            ok, _ = verify_lxp_credentials("agent@nalchik.ithub.ru", "pwd")
        self.assertTrue(ok)
        post.assert_called_once()


@override_settings(**REST_SETTINGS)
class VerifyUrlPathTests(TestCase):
    @patch("apps.integrations.services.lxp_auth.requests.post")
    def test_http_200_means_verified(self, post):
        post.return_value = _response(status_code=200)

        ok, message = verify_lxp_credentials("agent@nalchik.ithub.ru", "pwd")

        self.assertTrue(ok)
        self.assertEqual(message, "verified")

    @patch("apps.integrations.services.lxp_auth.requests.post")
    def test_non_200_means_wrong_credentials(self, post):
        post.return_value = _response(status_code=401)

        ok, message = verify_lxp_credentials("agent@nalchik.ithub.ru", "pwd")

        self.assertFalse(ok)
        self.assertIn("Invalid LXP", message)

    @patch("apps.integrations.services.lxp_auth.requests.post")
    def test_network_error_is_reported_as_unavailable(self, post):
        post.side_effect = requests.ConnectionError("down")

        ok, message = verify_lxp_credentials("agent@nalchik.ithub.ru", "pwd")

        self.assertFalse(ok)
        self.assertIn("unavailable", message)


@override_settings(**NO_LXP_SETTINGS)
class LocalPasswordFallbackTests(TestCase):
    def setUp(self):
        self.agent = make_agent(email="fallback@nalchik.ithub.ru", password="local-secret")

    @override_settings(DEBUG=True)
    def test_local_password_is_accepted_only_in_debug(self):
        ok, message = verify_lxp_credentials("fallback@nalchik.ithub.ru", "local-secret")

        self.assertTrue(ok)
        self.assertEqual(message, "verified")

    @override_settings(DEBUG=True)
    def test_email_lookup_ignores_case(self):
        """Почта колледжа приходит из разных источников в разном регистре."""
        ok, _ = verify_lxp_credentials("FallBack@Nalchik.ITHub.ru", "local-secret")

        self.assertTrue(ok)

    @override_settings(DEBUG=True)
    def test_wrong_local_password_is_rejected(self):
        ok, message = verify_lxp_credentials("fallback@nalchik.ithub.ru", "not-my-password")

        self.assertFalse(ok)
        self.assertIn("Invalid", message)

    @override_settings(DEBUG=True)
    def test_unknown_email_is_rejected(self):
        ok, message = verify_lxp_credentials("nobody@nalchik.ithub.ru", "local-secret")

        self.assertFalse(ok)
        self.assertIn("No user", message)

    @override_settings(DEBUG=False)
    def test_fallback_is_forbidden_without_debug(self):
        """В продакшене отсутствие настроек LXP — ошибка конфигурации, а не
        повод пускать по локальному паролю: иначе логин «через LXP» молча
        превращается в локальный."""
        with self.assertLogs("apps.integrations.services.lxp_auth", level="ERROR"):
            ok, message = verify_lxp_credentials("fallback@nalchik.ithub.ru", "local-secret")

        self.assertFalse(ok)
        self.assertIn("временно недоступен", message)

    @override_settings(DEBUG=False)
    @patch("apps.integrations.services.lxp_auth.requests.post")
    def test_no_external_request_is_made_without_settings(self, post):
        with self.assertLogs("apps.integrations.services.lxp_auth", level="ERROR"):
            verify_lxp_credentials("fallback@nalchik.ithub.ru", "local-secret")

        post.assert_not_called()
