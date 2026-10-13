"""Ночной забор проходов переживает отказ портала.

За три недели пилота пять ночей из пятнадцати пропали: «сессия истекла»,
«страница логина не сменилась», таймаут. Задача пробовала один раз и
сдавалась до следующего вечера, а учебный день терялся целиком.
"""

from __future__ import annotations

from unittest import mock

from celery.exceptions import Reject, Retry
from django.test import TestCase, override_settings

from apps.integrations.tasks import HIK_DAILY_RETRIES, fetch_hik_web_daily


@override_settings(HIK_DATA_MODE="browser")
class HikDailyRetryTests(TestCase):
    def setUp(self):
        # Вне воркера задача считает себя вызванной напрямую и повтор не
        # планирует: подкладываем контекст, как у настоящего запуска.
        fetch_hik_web_daily.push_request(retries=0, called_directly=False)
        self.addCleanup(fetch_hik_web_daily.pop_request)

    def test_temporary_failure_schedules_a_retry(self):
        with mock.patch(
            "apps.integrations.tasks.import_from_portal", side_effect=RuntimeError("Сессия истекла")
        ):
            with mock.patch("apps.integrations.services.hik_session.drop_session") as drop:
                # Вне воркера повтор некуда поставить: Celery оборачивает
                # его в Reject, но решение о повторе уже принято.
                with self.assertRaises((Retry, Reject)):
                    fetch_hik_web_daily(target_date_iso="2026-10-12")

        # Сессия сбрасывается перед повтором — с протухшими куками он
        # бессмысленен. Сколько именно раз, зависит от обёрток Celery.
        drop.assert_called()

    def test_fallback_only_after_retries_are_exhausted(self):
        fetch_hik_web_daily.push_request(retries=HIK_DAILY_RETRIES, called_directly=False)
        self.addCleanup(fetch_hik_web_daily.pop_request)

        with mock.patch(
            "apps.integrations.tasks.import_from_portal", side_effect=RuntimeError("Портал недоступен")
        ):
            with mock.patch(
                "apps.integrations.tasks.fetch_hik_browser_export_daily",
                return_value="hik_browser_error",
            ) as fallback:
                with mock.patch("apps.integrations.tasks.send_alert_to_admin") as alert:
                    result = fetch_hik_web_daily(target_date_iso="2026-10-12")

        fallback.assert_called_once()
        alert.assert_called_once()
        self.assertIn("hik_web_failed", result)

    def test_success_does_not_retry(self):
        run = mock.Mock(
            status="success", records_fetched=681, events_created=681, external_created=12, users_unmatched=0
        )
        with mock.patch(
            "apps.integrations.tasks.import_from_portal", return_value=mock.Mock(run=run)
        ):
            result = fetch_hik_web_daily(target_date_iso="2026-10-12")

        self.assertIn("records=681", result)

    @override_settings(HIK_DATA_MODE="off")
    def test_disabled_integration_is_not_retried(self):
        self.assertEqual(fetch_hik_web_daily(), "hik_off")
