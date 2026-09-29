"""«Без опозданий» не должно доставаться за неявку.

Закрытый прогон показал: квест засчитывался всем семнадцати студентам,
включая двоих, у которых нет ни одного прохода. Отсутствие данных о людях
принималось за доказательство дисциплины.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.quests.services.verifiers import verify_hik_no_late

User = get_user_model()
PAST = date(2026, 9, 22)


class HikNoLateEvidenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="agent", email="a@test.ru", password="x", callsign="Агент"
        )

    def verify(self, by_day: dict, target: date = PAST, days: int = 1):
        with mock.patch(
            "apps.quests.services.verifiers._hik_events_for_user_in_range", return_value=by_day
        ):
            return verify_hik_no_late(self.user, {"days": days}, target)

    def test_no_passes_at_all_is_not_a_completed_quest(self):
        result = self.verify({})

        self.assertFalse(result.completed)
        self.assertIn("Нет проходов", result.message)

    def test_passes_without_late_events_complete_the_quest(self):
        result = self.verify({PAST: [{"event_type": "access"}]})

        self.assertTrue(result.completed)
        self.assertEqual(result.evidence["days_with_data"], 1)

    def test_late_event_fails_the_quest(self):
        result = self.verify({PAST: [{"event_type": "late"}]})

        self.assertFalse(result.completed)
        self.assertEqual(result.evidence["late_days"], [PAST.isoformat()])

    def test_today_without_data_is_still_pending(self):
        """Сегодняшние проходы могут прийти вечером — это не отказ."""
        today = timezone.now().date()

        result = self.verify({}, target=today)

        self.assertFalse(result.completed)
        self.assertTrue(result.evidence["pending"])

    def test_week_counts_only_days_with_data(self):
        result = self.verify(
            {PAST: [{"event_type": "access"}], PAST - timedelta(days=1): []}, days=5
        )

        self.assertTrue(result.completed)
        self.assertEqual(result.evidence["days_with_data"], 1)
