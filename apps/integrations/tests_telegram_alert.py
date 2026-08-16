from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.integrations.services.telegram_alert import format_alert_message, send_alert_to_admin


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "alert-tests"}},
    TELEGRAM_BOT_TOKEN="tok",
    TELEGRAM_ADMIN_CHAT_ID="123",
    TELEGRAM_ALERTS_ENABLED=True,
    TELEGRAM_ALERT_DEDUP_TTL=3600,
    ENVIRONMENT_NAME="test",
)
class TelegramAlertTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch("apps.integrations.services.telegram_alert.send_admin_alert", return_value=(True, "ok"))
    def test_dedup_blocks_second_send(self, mock_send):
        self.assertTrue(
            send_alert_to_admin(
                title="T1",
                message="m",
                deduplicate_key="dup_key",
                is_critical=False,
            )
        )
        self.assertFalse(
            send_alert_to_admin(
                title="T1",
                message="m",
                deduplicate_key="dup_key",
                is_critical=False,
            )
        )
        self.assertEqual(mock_send.call_count, 1)

    @patch("apps.integrations.services.telegram_alert.send_admin_alert", return_value=(True, "ok"))
    def test_critical_alerts_are_also_deduplicated(self, mock_send):
        """Критичные алерты тоже дедуплицируются — просто окно короче.

        Celery шлёт все падения задач как критичные, и раньше дедупликация
        к ним не применялась вовсе: одна регулярно падающая задача заливала
        чат одинаковыми сообщениями, где терялось всё остальное.
        """
        send_alert_to_admin(title="C1", message="m", deduplicate_key="crit", is_critical=True)
        send_alert_to_admin(title="C2", message="m", deduplicate_key="crit", is_critical=True)
        self.assertEqual(mock_send.call_count, 1)

    @patch("apps.integrations.services.telegram_alert.send_admin_alert", return_value=(True, "ok"))
    def test_alerts_without_key_are_always_sent(self, mock_send):
        send_alert_to_admin(title="A", message="m", is_critical=True)
        send_alert_to_admin(title="B", message="m", is_critical=True)
        self.assertEqual(mock_send.call_count, 2)

    @override_settings(TELEGRAM_ALERTS_ENABLED=False)
    @patch("apps.integrations.services.telegram_alert.send_admin_alert")
    def test_disabled_no_send(self, mock_send):
        self.assertFalse(send_alert_to_admin(title="X", message="m"))
        mock_send.assert_not_called()

    def test_jwt_is_masked_in_alert_body(self):
        """Текст исключения из LXP уходил в чат вместе с accessToken."""
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        text = format_alert_message("T", f"Ответ LXP: {jwt}", "lxp")
        self.assertNotIn(jwt, text)
        self.assertIn("<токен скрыт>", text)

    def test_credentials_in_key_value_form_are_masked(self):
        text = format_alert_message(
            "T",
            'Тело: {"accessToken": "abc123secret", "password": "hunter2"}',
            "auth",
        )
        self.assertNotIn("abc123secret", text)
        self.assertNotIn("hunter2", text)

    def test_ordinary_text_is_not_mangled(self):
        text = format_alert_message("T", "Не удалось разобрать 5 из 120 событий", "hik")
        self.assertIn("Не удалось разобрать 5 из 120 событий", text)

    def test_format_contains_title_and_env(self):
        text = format_alert_message("My Title", "body", "lxp")
        self.assertIn("My Title", text)
        self.assertIn("test", text)
        self.assertIn("body", text)
