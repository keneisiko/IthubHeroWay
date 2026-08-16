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
        self.assertTrue(
            RatingLog.objects.filter(user=u, source_id=f"hik-late:{u.pk}:2026-06-01").exists()
        )

    def test_user_is_matched_by_email_when_card_number_is_empty(self):
        """Портал отдаёт cardNumber пустым во всех записях, но присылает почту."""
        squad = Squad.objects.create(code="S5", name="Отряд 5")
        Schedule.objects.create(
            squad=squad,
            day_of_week=DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(16, 30),
        )
        u = User.objects.create_user(
            username="byemail",
            email="Student@nalchik.ithub.ru",
            password="x",
            callsign="byemail_call",
            squad=squad,
            rating_current=300,
        )
        tz = timezone.get_current_timezone()
        HikEvent.objects.create(
            event_id="portal-guid-1",
            student_code="",
            event_time=timezone.make_aware(datetime(2026, 6, 1, 9, 8), tz),
            event_type="access",
            door_name="Вход",
            raw_data={"personEmail": "student@nalchik.ithub.ru", "direction": 1},
        )

        process_unprocessed_hik_events(limit=10)

        ev = ExternalEvent.objects.get(source="hik", external_event_id="portal-guid-1")
        self.assertEqual(ev.payload.get("user_id"), u.pk)
        self.assertTrue(ev.payload.get("is_entry"))

    def test_exit_pass_is_not_penalized(self):
        """direction=2 — выход с занятий, опозданием он быть не может."""
        squad = Squad.objects.create(code="S6", name="Отряд 6")
        Schedule.objects.create(
            squad=squad,
            day_of_week=DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(16, 30),
        )
        u = User.objects.create_user(
            username="exituser",
            email="exit@test.ru",
            password="x",
            callsign="exit_call",
            hik_card_code="CARD-E",
            squad=squad,
            rating_current=300,
        )
        tz = timezone.get_current_timezone()
        HikEvent.objects.create(
            event_id="portal-guid-exit",
            student_code="CARD-E",
            event_time=timezone.make_aware(datetime(2026, 6, 1, 14, 30), tz),
            event_type="access",
            door_name="Выход",
            raw_data={"direction": 2},
        )

        process_unprocessed_hik_events(limit=10)

        u.refresh_from_db()
        self.assertEqual(u.rating_current, 300)
        self.assertFalse(
            RatingLog.objects.filter(user=u, source_id__startswith="hik-late:").exists()
        )

    def test_multiple_passes_in_one_day_are_penalized_once(self):
        """Выход в перерыве и возвращение не должны штрафоваться повторно."""
        squad = Squad.objects.create(code="S3", name="Отряд 3")
        Schedule.objects.create(
            squad=squad,
            day_of_week=DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(16, 30),
        )
        u = User.objects.create_user(
            username="multiuser",
            email="m@test.ru",
            password="x",
            callsign="multi_call",
            hik_card_code="CARD-M",
            squad=squad,
            rating_current=300,
        )
        tz = timezone.get_current_timezone()
        for idx, moment in enumerate(
            [
                datetime(2026, 6, 1, 9, 8),
                datetime(2026, 6, 1, 12, 30),
                datetime(2026, 6, 1, 14, 15),
            ]
        ):
            HikEvent.objects.create(
                event_id=f"HIK-MULTI-{idx}",
                student_code="CARD-M",
                event_time=timezone.make_aware(moment, tz),
                event_type="entry",
                door_name="Main",
                raw_data={},
            )

        process_unprocessed_hik_events(limit=10)

        # Три прохода — три ExternalEvent, но ровно один штраф за день.
        self.assertEqual(ExternalEvent.objects.filter(source="hik").count(), 3)
        penalties = RatingLog.objects.filter(user=u, source_id__startswith="hik-late:")
        self.assertEqual(penalties.count(), 1)
        u.refresh_from_db()
        self.assertEqual(u.rating_current, 297)

    def test_reprocessing_same_day_does_not_penalize_twice(self):
        """Повторный импорт той же выгрузки не должен списывать рейтинг снова."""
        squad = Squad.objects.create(code="S4", name="Отряд 4")
        Schedule.objects.create(
            squad=squad,
            day_of_week=DayOfWeek.MONDAY,
            start_time=time(9, 0),
            end_time=time(16, 30),
        )
        u = User.objects.create_user(
            username="reimport",
            email="r@test.ru",
            password="x",
            callsign="reimport_call",
            hik_card_code="CARD-R",
            squad=squad,
            rating_current=300,
        )
        tz = timezone.get_current_timezone()
        HikEvent.objects.create(
            event_id="HIK-RE-1",
            student_code="CARD-R",
            event_time=timezone.make_aware(datetime(2026, 6, 1, 9, 8), tz),
            event_type="entry",
            door_name="Main",
            raw_data={},
        )
        process_unprocessed_hik_events(limit=10)

        # Та же дата, другое событие (как при повторной выгрузке за день).
        HikEvent.objects.create(
            event_id="HIK-RE-2",
            student_code="CARD-R",
            event_time=timezone.make_aware(datetime(2026, 6, 1, 9, 9), tz),
            event_type="entry",
            door_name="Main",
            raw_data={},
        )
        process_unprocessed_hik_events(limit=10)

        u.refresh_from_db()
        self.assertEqual(u.rating_current, 297)
        self.assertEqual(
            RatingLog.objects.filter(user=u, source_id__startswith="hik-late:").count(), 1
        )
