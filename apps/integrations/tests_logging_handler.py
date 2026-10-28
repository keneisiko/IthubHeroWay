"""Ошибки из логов уходят администратору в Telegram, одинаковые — один раз."""

from __future__ import annotations

import logging
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.integrations.logging_handlers import TelegramErrorHandler

SEND = "apps.integrations.services.telegram_alert.send_alert_to_admin"


class TelegramErrorHandlerTests(SimpleTestCase):
    def setUp(self):
        self.logger = logging.getLogger("apps.quests.test_handler")
        self.handler = TelegramErrorHandler()
        self.logger.addHandler(self.handler)
        self.addCleanup(self.logger.removeHandler, self.handler)

    @patch(SEND)
    def test_exception_is_sent_with_place_and_traceback(self, send):
        try:
            raise ValueError("boom")
        except ValueError:
            self.logger.exception("quest_verify_failed quest=%s", "q1")
        message = send.call_args.kwargs["message"]
        self.assertIn("quest_verify_failed quest=q1", message)
        self.assertIn("ValueError: boom", message)
        self.assertIn("Где:", message)

    @patch(SEND)
    def test_same_error_different_values_share_dedup_key(self, send):
        for user_id in (1, 2):  # один вызов в цикле, как проверка по всем студентам
            self.logger.error("failed user=%s", user_id)
        keys = {call.kwargs["deduplicate_key"] for call in send.call_args_list}
        self.assertEqual(len(keys), 1)

    @patch(SEND)
    def test_warning_and_alert_channel_errors_are_not_sent(self, send):
        self.logger.warning("just a warning")
        logging.getLogger("apps.integrations.services.telegram_alert").addHandler(self.handler)
        logging.getLogger("apps.integrations.services.telegram_alert").error("send failed")
        logging.getLogger("apps.integrations.services.telegram_alert").removeHandler(self.handler)
        send.assert_not_called()

    @patch(SEND, side_effect=RuntimeError("telegram down"))
    def test_broken_alert_channel_does_not_break_logging(self, _send):
        self.logger.error("still fine")
