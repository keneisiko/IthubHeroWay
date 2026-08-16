"""Тесты журнала импорта Hik.

Смысл журнала: раньше «данных нет» и «интеграция сломалась» давали одинаковую
строку с нулями и одинаково считались успехом.
"""

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from apps.integrations.models import HikImportRun, HikImportStatus
from apps.integrations.services.hik_import import import_from_portal
from apps.integrations.services.hik_web_client import HikWebAuthError
from apps.integrations.services.hik_web_fetch import HikFetchResult, day_bounds


def fetch_result(rows, relogin=False) -> HikFetchResult:
    start, end = day_bounds(date(2026, 6, 15))
    return HikFetchResult(start=start, end=end, rows=rows, relogin_used=relogin)


def portal_row(guid: str) -> dict:
    return {
        "eventId": guid,
        "personCode": "STU-1",
        "personEmail": "s@nalchik.ithub.ru",
        "eventTime": "2026-06-15T09:05:00+03:00",
        "eventType": "access",
        "doorName": "Вход",
        "direction": 1,
        "isEntry": True,
        "authOk": True,
    }


class ImportJournalTests(TestCase):
    @patch("apps.integrations.services.hik_import.fetch_rows_for_range")
    def test_successful_import_is_recorded(self, fetch):
        fetch.return_value = fetch_result([portal_row("g1"), portal_row("g2")])

        outcome = import_from_portal(date(2026, 6, 15), date(2026, 6, 15))

        run = HikImportRun.objects.get()
        self.assertEqual(run.status, HikImportStatus.SUCCESS)
        self.assertEqual(run.records_fetched, 2)
        self.assertEqual(run.events_created, 2)
        self.assertTrue(outcome.ok)

    @patch("apps.integrations.services.hik_import.fetch_rows_for_range")
    def test_empty_period_is_not_an_error(self, fetch):
        """Каникулы и выключенные турникеты — отдельный статус, не ошибка."""
        fetch.return_value = fetch_result([])

        outcome = import_from_portal(date(2026, 8, 15), date(2026, 8, 15))

        run = HikImportRun.objects.get()
        self.assertEqual(run.status, HikImportStatus.EMPTY)
        self.assertEqual(run.records_fetched, 0)
        self.assertTrue(outcome.ok)

    @patch("apps.integrations.services.hik_import.fetch_rows_for_range")
    def test_failure_is_recorded_and_reraised(self, fetch):
        fetch.side_effect = HikWebAuthError("denied")

        with self.assertRaises(HikWebAuthError):
            import_from_portal(date(2026, 6, 15), date(2026, 6, 15))

        run = HikImportRun.objects.get()
        self.assertEqual(run.status, HikImportStatus.ERROR)
        self.assertIn("denied", run.error)

    @patch("apps.integrations.services.hik_import.fetch_rows_for_range")
    def test_repeated_import_of_same_data_creates_no_duplicates(self, fetch):
        """Повторный прогон за ту же дату не должен плодить события."""
        fetch.return_value = fetch_result([portal_row("g1"), portal_row("g2")])

        import_from_portal(date(2026, 6, 15), date(2026, 6, 15))
        import_from_portal(date(2026, 6, 15), date(2026, 6, 15))

        runs = HikImportRun.objects.order_by("started_at")
        self.assertEqual(runs[0].events_created, 2)
        self.assertEqual(runs[1].events_created, 0)

    @patch("apps.integrations.services.hik_import.fetch_rows_for_range")
    def test_relogin_flag_is_stored(self, fetch):
        fetch.return_value = fetch_result([portal_row("g1")], relogin=True)

        import_from_portal(date(2026, 6, 15), date(2026, 6, 15))

        self.assertTrue(HikImportRun.objects.get().relogin_used)
