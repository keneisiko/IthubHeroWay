"""Тесты связки «сессия + клиент»: границы суток и повторный вход по 401."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.integrations.services import hik_web_fetch
from apps.integrations.services.hik_web_client import HikWebAuthError


@override_settings(TIME_ZONE="Europe/Moscow", USE_TZ=True)
class DayBoundsTests(TestCase):
    def test_bounds_are_local_not_utc(self):
        """Сутки считаются по московскому времени: иначе утренние проходы
        уезжают в предыдущий день и ломают расчёт опозданий."""
        start, end = hik_web_fetch.day_bounds(date(2026, 6, 15))
        local_start = timezone.localtime(start)
        local_end = timezone.localtime(end)

        self.assertEqual((local_start.hour, local_start.minute), (0, 0))
        self.assertEqual((local_end.hour, local_end.minute), (23, 59))
        self.assertEqual(local_start.date(), date(2026, 6, 15))
        self.assertEqual(local_end.date(), date(2026, 6, 15))
        self.assertIsNotNone(start.tzinfo)


class FetchRetryTests(TestCase):
    def setUp(self):
        self.start, self.end = hik_web_fetch.day_bounds(date(2026, 6, 15))

    @patch("apps.integrations.services.hik_web_fetch.get_session_cookies")
    @patch("apps.integrations.services.hik_web_fetch.HikWebClient")
    def test_happy_path_uses_cached_session(self, client_cls, get_cookies):
        get_cookies.return_value = {"sid": "cached"}
        client_cls.return_value.fetch_rows.return_value = [{"eventId": "g1"}]

        result = hik_web_fetch.fetch_rows_for_range(self.start, self.end)

        self.assertEqual(result.count, 1)
        self.assertFalse(result.relogin_used)
        get_cookies.assert_called_once_with()

    @patch("apps.integrations.services.hik_web_fetch.drop_session")
    @patch("apps.integrations.services.hik_web_fetch.get_session_cookies")
    @patch("apps.integrations.services.hik_web_fetch.HikWebClient")
    def test_expired_session_triggers_single_relogin(self, client_cls, get_cookies, drop):
        get_cookies.side_effect = [{"sid": "stale"}, {"sid": "fresh"}]
        client_cls.return_value.fetch_rows.side_effect = [
            HikWebAuthError("Login timed out"),
            [{"eventId": "g1"}, {"eventId": "g2"}],
        ]

        result = hik_web_fetch.fetch_rows_for_range(self.start, self.end)

        self.assertEqual(result.count, 2)
        self.assertTrue(result.relogin_used)
        drop.assert_called_once()
        self.assertEqual(get_cookies.call_count, 2)
        self.assertTrue(get_cookies.call_args_list[1].kwargs["force_refresh"])

    @patch("apps.integrations.services.hik_web_fetch.drop_session")
    @patch("apps.integrations.services.hik_web_fetch.get_session_cookies")
    @patch("apps.integrations.services.hik_web_fetch.HikWebClient")
    def test_auth_error_after_relogin_is_raised(self, client_cls, get_cookies, drop):
        """Дважды 401 — это проблема доступа, а не протухшая сессия;
        молча возвращать ноль событий нельзя."""
        get_cookies.side_effect = [{"sid": "a"}, {"sid": "b"}]
        client_cls.return_value.fetch_rows.side_effect = HikWebAuthError("denied")

        with self.assertRaises(HikWebAuthError):
            hik_web_fetch.fetch_rows_for_range(self.start, self.end)
