"""Серии без опозданий не считались вовсе.

Два изъяна, найденных при проверке остальных квестов после закрытого
прогона: расчёт брал только привязанных к Telegram, а без заведённого
расписания считал, что пар не было ни в один день.
"""

from __future__ import annotations

from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.models import Role, Squad
from apps.progress.services.strike_bonuses import _has_classes
from apps.schedule.models import Schedule

User = get_user_model()


class HasClassesFallbackTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="itr2-24", name="3ИТР2.9.24", course=3)
        self.user = User.objects.create_user(
            username="agent", email="a@test.ru", password="x", callsign="Агент", squad=self.squad
        )

    def test_weekdays_count_as_school_days_without_schedule(self):
        monday = date(2026, 9, 21)

        self.assertTrue(_has_classes(self.user, monday))

    def test_weekend_is_not_a_school_day_without_schedule(self):
        sunday = date(2026, 9, 27)

        self.assertFalse(_has_classes(self.user, sunday))

    def test_loaded_schedule_wins_over_the_fallback(self):
        """Заведённое расписание — источник правды, догадки отключаются."""
        Schedule.objects.create(
            squad=self.squad,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(10, 30),
            is_active=True,
        )

        self.assertTrue(_has_classes(self.user, date(2026, 9, 22)))
        self.assertFalse(_has_classes(self.user, date(2026, 9, 21)))

    def test_student_without_squad_is_left_alone(self):
        homeless = User.objects.create_user(
            username="homeless", email="h@test.ru", password="x", callsign="Бездомный"
        )

        self.assertFalse(_has_classes(homeless, date(2026, 9, 21)))


class StrikeAudienceTests(TestCase):
    @override_settings(REQUIRE_TELEGRAM_LINK_FOR_SCORING=False)
    def test_closed_pilot_students_are_counted(self):
        from apps.integrations.services.account_gate import agents_for_scoring

        squad = Squad.objects.create(code="itr2-24", name="3ИТР2.9.24", course=3)
        User.objects.create_user(
            username="agent",
            email="a@test.ru",
            password="x",
            callsign="Агент",
            squad=squad,
            role=Role.AGENT,
        )

        self.assertEqual(agents_for_scoring(User.objects.all()).count(), 1)
