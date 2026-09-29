"""Серии и пропуски.

Два изъяна, найденные на пилоте. Пропуск не рвал серию без опозданий:
тот, кто приходит раз в неделю и не опаздывает, за месяц набирал недельную
серию. А сравнение с календарным «вчера» обнуляло серии каждый понедельник:
выходные выглядели пропуском.
"""

from __future__ import annotations

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Squad
from apps.progress.services.strike_bonuses import (
    MISSED_DAYS_BREAKING_STREAK,
    missed_school_days,
    previous_school_day,
)
from apps.schedule.models import Schedule

User = get_user_model()

MONDAY = date(2026, 9, 21)
FRIDAY = date(2026, 9, 25)


class SchoolDayArithmeticTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="itr2-24", name="3ИТР2.9.24", course=3)
        self.user = User.objects.create_user(
            username="agent", email="a@test.ru", password="x", callsign="Агент", squad=self.squad
        )
        # Пары по будням: понедельник–пятница.
        for weekday in range(5):
            Schedule.objects.create(
                squad=self.squad,
                day_of_week=weekday,
                start_time=time(9, 0),
                end_time=time(10, 30),
                is_active=True,
            )

    def test_monday_follows_friday(self):
        """Выходные не пропуск: иначе серия рвалась каждую неделю."""
        next_monday = MONDAY + timedelta(days=7)

        self.assertEqual(previous_school_day(self.user, next_monday), FRIDAY)

    def test_previous_day_of_tuesday_is_monday(self):
        tuesday = date(2026, 9, 22)

        self.assertEqual(previous_school_day(self.user, tuesday), MONDAY)

    def test_weekend_does_not_count_as_missed(self):
        """Пятница → понедельник: пропущенных учебных дней нет."""
        monday_next = date(2026, 9, 28)

        self.assertEqual(missed_school_days(self.user, FRIDAY, monday_next), 1)

    def test_three_missed_days_reach_the_limit(self):
        # Был в понедельник, следующий разбираемый день — четверг.
        self.assertGreaterEqual(
            missed_school_days(self.user, MONDAY, date(2026, 9, 24)), MISSED_DAYS_BREAKING_STREAK
        )

    def test_no_anchor_means_nothing_missed(self):
        self.assertEqual(missed_school_days(self.user, None, FRIDAY), 0)


class ScheduleAwareStreakTests(TestCase):
    """Без расписания в силе запасной вариант: учебными считаются будни."""

    def setUp(self):
        self.squad = Squad.objects.create(code="plain", name="Без расписания", course=1)
        self.user = User.objects.create_user(
            username="agent2", email="a2@test.ru", password="x", callsign="Агент2", squad=self.squad
        )

    def test_weekend_skipped_without_schedule_too(self):
        monday = date(2026, 9, 28)

        self.assertEqual(previous_school_day(self.user, monday), date(2026, 9, 25))
