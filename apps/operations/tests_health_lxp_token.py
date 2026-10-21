"""Монитор здоровья и токен LXP.

20–21.10.2026 монитор слал «LXP токен отсутствует в кеше», хотя все ночные
задачи получили токен и отработали: пустой кеш — нормальное состояние
(токен живёт 23 часа, обновляется раз в 24), и любая задача при промахе
сама входит в LXP. Тревога должна быть только когда LXP не пускает.
"""

from __future__ import annotations

from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.integrations.services.lxp_graphql_client import LXPAuthError, LXPGraphQLClient
from apps.operations.services.health_monitor import _lxp_token_issue

CLIENT = "apps.operations.services.health_monitor.LXPGraphQLClient"


@override_settings(LXP_API_TOKEN="")
class LxpTokenHealthTests(TestCase):
    def setUp(self):
        cache.delete(LXPGraphQLClient.TOKEN_CACHE_KEY)
        self.addCleanup(cache.delete, LXPGraphQLClient.TOKEN_CACHE_KEY)

    def test_cached_token_is_fine_without_login(self):
        cache.set(LXPGraphQLClient.TOKEN_CACHE_KEY, "t" * 50, 60)

        with mock.patch.object(LXPGraphQLClient, "get_token") as get_token:
            self.assertEqual(_lxp_token_issue(), "")

        get_token.assert_not_called()

    def test_empty_cache_is_not_an_alarm_when_login_works(self):
        """Именно это и случалось каждую ночь с 00:45 до 01:45."""
        with mock.patch.object(LXPGraphQLClient, "get_token", return_value="fresh"):
            self.assertEqual(_lxp_token_issue(), "")

    def test_real_login_failure_is_reported_with_reason(self):
        with mock.patch.object(LXPGraphQLClient, "get_token", side_effect=LXPAuthError("неверный пароль")):
            issue = _lxp_token_issue()

        self.assertIn("LXP не выдаёт токен", issue)
        self.assertIn("неверный пароль", issue)
