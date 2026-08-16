"""Тесты входа бота в LXP (LXPGraphQLClient.login).

Главное здесь — не «работает ли вход», а что текст исключения безопасен.
Ошибка из login() уходит в Telegram-алерт админу и в логи через get_token(),
и раньше туда попадало целиком тело ответа портала — вместе с accessToken и
refreshToken. Тесты фиксируют, что ни токен, ни тело ответа в сообщение
не возвращаются ни на одной ветке ошибки.
"""

from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.integrations.services.lxp_graphql_client import LXPAuthError, LXPGraphQLClient

SECRET_ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJib3QifQ.s3cr3t-4ccess"
SECRET_REFRESH_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJyIjoiMSJ9.s3cr3t-r3fr3sh"

LXP_TEST_SETTINGS = dict(
    LXP_GRAPHQL_ENDPOINT="https://api.example.test/graphql",
    LXP_API_TOKEN="",
    LXP_BOT_EMAIL="bot@example.test",
    LXP_BOT_PASSWORD="bot-password",
    LXP_USE_BROWSER_TOKEN_BOT=False,
)


def _response(*, status_code=200, json_value=None, json_error=None, text=""):
    """Мок requests.Response с управляемым поведением .json()."""
    resp = Mock()
    resp.status_code = status_code
    resp.text = text
    resp.content = (text or "x").encode()
    if json_error is not None:
        resp.json.side_effect = json_error
    else:
        resp.json.return_value = json_value
    return resp


@override_settings(**LXP_TEST_SETTINGS)
class LoginSuccessTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    @patch("apps.integrations.services.lxp_graphql_client.requests.post")
    def test_login_caches_access_token_and_drops_refresh_token(self, post):
        """refresh-токен намеренно не сохраняется: мутации обновления в клиенте нет.

        Раньше он лежал в кеше вдвое дольше основного и никем не читался —
        лишний секрет в Redis без применения.
        """
        post.return_value = _response(
            json_value={
                "data": {
                    "signIn": {
                        "accessToken": SECRET_ACCESS_TOKEN,
                        "refreshToken": SECRET_REFRESH_TOKEN,
                    }
                }
            }
        )

        token = LXPGraphQLClient().login()

        self.assertEqual(token, SECRET_ACCESS_TOKEN)
        self.assertEqual(cache.get(LXPGraphQLClient.TOKEN_CACHE_KEY), SECRET_ACCESS_TOKEN)
        self.assertIsNone(cache.get(f"{LXPGraphQLClient.TOKEN_CACHE_KEY}_refresh"))


@override_settings(**LXP_TEST_SETTINGS)
class LoginErrorBranchTests(SimpleTestCase):
    """Каждая ветка ошибки: понятный текст и никаких секретов внутри."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def assert_no_secrets(self, message: str):
        # Сравниваем со значениями секретов, а не с именами полей: слово
        # accessToken в подсказке «проверьте логин/пароль» безобидно.
        for secret in (SECRET_ACCESS_TOKEN, SECRET_REFRESH_TOKEN, "bot-password"):
            self.assertNotIn(secret, message)

    @patch("apps.integrations.services.lxp_graphql_client.requests.post")
    def test_http_500_reports_status_only(self, post):
        post.return_value = _response(
            status_code=500,
            text=f'{{"data":{{"signIn":{{"accessToken":"{SECRET_ACCESS_TOKEN}"}}}}}}',
        )

        with self.assertRaises(LXPAuthError) as ctx:
            LXPGraphQLClient().login()

        message = str(ctx.exception)
        self.assertIn("500", message)
        self.assert_no_secrets(message)
        self.assertIsNone(cache.get(LXPGraphQLClient.TOKEN_CACHE_KEY))

    @patch("apps.integrations.services.lxp_graphql_client.requests.post")
    def test_invalid_json_does_not_leak_body(self, post):
        """Портал за WAF отдаёт HTML-заглушку; её нельзя пересылать в алерт."""
        post.return_value = _response(
            json_error=ValueError("no json"),
            text="<html>login page with hidden secret</html>",
        )

        with self.assertRaises(LXPAuthError) as ctx:
            LXPGraphQLClient().login()

        message = str(ctx.exception)
        self.assertIn("не JSON", message)
        self.assertNotIn("<html>", message)
        self.assert_no_secrets(message)

    @patch("apps.integrations.services.lxp_graphql_client.requests.post")
    def test_graphql_errors_keep_only_messages(self, post):
        """Из ошибок GraphQL берём сообщения, но не extensions и не переменные запроса."""
        post.return_value = _response(
            json_value={
                "errors": [
                    {
                        "message": "Invalid credentials",
                        "extensions": {"password": "bot-password"},
                    }
                ],
                "data": None,
            }
        )

        with self.assertRaises(LXPAuthError) as ctx:
            LXPGraphQLClient().login()

        message = str(ctx.exception)
        self.assertIn("Invalid credentials", message)
        self.assert_no_secrets(message)

    @patch("apps.integrations.services.lxp_graphql_client.requests.post")
    def test_graphql_errors_without_message_do_not_crash(self, post):
        post.return_value = _response(json_value={"errors": ["strange"], "data": None})

        with self.assertRaises(LXPAuthError) as ctx:
            LXPGraphQLClient().login()

        self.assertIn("без сообщения", str(ctx.exception))

    @patch("apps.integrations.services.lxp_graphql_client.requests.post")
    def test_missing_access_token_points_at_credentials(self, post):
        post.return_value = _response(
            json_value={"data": {"signIn": {"refreshToken": SECRET_REFRESH_TOKEN}}}
        )

        with self.assertRaises(LXPAuthError) as ctx:
            LXPGraphQLClient().login()

        message = str(ctx.exception)
        self.assertIn("LXP_BOT_EMAIL", message)
        self.assertNotIn(SECRET_REFRESH_TOKEN, message)
        self.assertIsNone(cache.get(LXPGraphQLClient.TOKEN_CACHE_KEY))

    @patch("apps.integrations.services.lxp_graphql_client.requests.post")
    def test_network_error_reports_exception_type_only(self, post):
        """Текст requests-исключения содержит URL с параметрами — в алерт он не нужен."""
        post.side_effect = requests.ConnectionError(
            f"failed to connect https://api.example.test/graphql?token={SECRET_ACCESS_TOKEN}"
        )

        with self.assertRaises(LXPAuthError) as ctx:
            LXPGraphQLClient().login()

        message = str(ctx.exception)
        self.assertIn("ConnectionError", message)
        self.assert_no_secrets(message)

    @patch("apps.integrations.services.lxp_graphql_client.requests.post")
    def test_login_does_not_leak_token_in_any_error_branch(self, post):
        """Сводная проверка: секрет не должен всплыть ни в одном сценарии отказа."""
        leaky_body = {
            "data": {
                "signIn": {
                    "accessToken": SECRET_ACCESS_TOKEN,
                    "refreshToken": SECRET_REFRESH_TOKEN,
                }
            },
            "errors": [{"message": f"debug dump {SECRET_ACCESS_TOKEN}"[:9]}],
        }
        branches = [
            _response(status_code=401, text=str(leaky_body)),
            _response(json_error=ValueError("boom"), text=str(leaky_body)),
            _response(json_value=leaky_body),
            _response(json_value={"data": {"signIn": {}}}),
        ]
        for response in branches:
            with self.subTest(status=response.status_code):
                post.return_value = response
                with self.assertRaises(LXPAuthError) as ctx:
                    LXPGraphQLClient().login()
                self.assert_no_secrets(str(ctx.exception))


class LoginConfigurationTests(SimpleTestCase):
    @override_settings(LXP_BOT_EMAIL="", LXP_BOT_PASSWORD="", LXP_API_TOKEN="")
    @patch("apps.integrations.services.lxp_graphql_client.requests.post")
    def test_missing_credentials_fail_before_any_request(self, post):
        """Без логина и пароля запрос уходить не должен — иначе портал видит пустой вход."""
        with self.assertRaises(LXPAuthError):
            LXPGraphQLClient().login()
        post.assert_not_called()

    @override_settings(LXP_USE_BROWSER_TOKEN_BOT=True, **{
        k: v for k, v in LXP_TEST_SETTINGS.items() if k != "LXP_USE_BROWSER_TOKEN_BOT"
    })
    @patch("apps.integrations.services.lxp_graphql_client.LXPGraphQLClient.login_via_browser")
    def test_browser_mode_delegates_without_http_login(self, login_via_browser):
        login_via_browser.return_value = "browser-token"

        self.assertEqual(LXPGraphQLClient().login(), "browser-token")
        login_via_browser.assert_called_once_with()
