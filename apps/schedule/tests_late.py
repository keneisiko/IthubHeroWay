from __future__ import annotations

from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Squad
from apps.integrations.models import ExternalEvent, HikEvent
from apps.integrations.services.hik_attendance_processor import process_unprocessed_hik_events
from apps.progress.models import RatingLog
from apps.progress.services.late_penalties import late_penalty_delta
from apps.schedule.models import DayOfWeek, Schedule
from apps.schedule.services import classify_entrance_against_schedule

User = get_user_model()


class LatePenaltyTests(TestCase):
    @override_settings(RATING_KP={"LATE_LIGHT": -3, "LATE_MODERATE": -5, "LATE_SEVERE": -8})
    def test_penalty_tiers(self):
        self.assertEqual(late_penalty_delta(5), -3)
        self.assertEqual(late_penalty_delta(10), -3)
        self.assertEqual(late_penalty_delta(12), -5)
        self.assertEqual(late_penalty_delta(20), -8)


class ScheduleClassificationTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="S1", name="Отряд 1")
        Schedule.objects.create(
            squad=self.squad,
            day_of_week=DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(10, 30),
            discipline="Python",
        )

    def test_on_time_before_start(self):
        tz = timezone.get_current_timezone()
        event_dt = timezone.make_aware(datetime(2026, 6, 1, 8, 55), tz)  # Monday
        result = classify_entrance_against_schedule(squad_id=self.squad.pk, event_dt=event_dt)
        self.assertEqual(result["event_type"], "access")
        self.assertEqual(result["late_minutes"], 0)

    def test_late_after_start(self):
        tz = timezone.get_current_timezone()
        event_dt = timezone.make_aware(datetime(2026, 6, 1, 9, 12), tz)
        result = classify_entrance_against_schedule(squad_id=self.squad.pk, event_dt=event_dt)
        self.assertEqual(result["event_type"], "late")
        self.assertEqual(result["late_minutes"], 12)


class HikLateIntegrationTests(TestCase):
    def test_late_creates_external_event_and_penalty(self):
        squad = Squad.objects.create(code="S2", name="Отряд 2")
        Schedule.objects.create(
            squad=squad,
            day_of_week=DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(10, 30),
        )
        u = User.objects.create_user(
            username="lateuser",
            email="l@test.ru",
            password="x",
            callsign="late_call",
            hik_card_code="CARD-L",
            squad=squad,
            rating_current=300,
        )
        tz = timezone.get_current_timezone()
        event_time = timezone.make_aware(datetime(2026, 6, 1, 9, 8), tz)
        HikEvent.objects.create(
            event_id="HIK-LATE-1",
            student_code="CARD-L",
            event_time=event_time,
            event_type="entry",
            door_name="Main",
            raw_data={},
        )
        process_unprocessed_hik_events(limit=10)
        ev = ExternalEvent.objects.get(source="hik", external_event_id="HIK-LATE-1")
        self.assertEqual(ev.payload.get("event_type"), "late")
        self.assertEqual(ev.payload.get("late_minutes"), 8)
        u.refresh_from_db()
        self.assertEqual(u.rating_current, 297)
        self.assertTrue(RatingLog.objects.filter(user=u, source_id="hik-late:HIK-LATE-1").exists())
