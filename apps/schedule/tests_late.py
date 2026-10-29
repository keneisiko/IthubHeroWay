from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Squad
from apps.integrations.models import ExternalEvent, HikEvent
from apps.integrations.services.hik_attendance_processor import process_unprocessed_hik_events
from apps.progress.models import RatingLog
from apps.schedule.models import DayOfWeek, Schedule
from apps.schedule.services import classify_entrance_against_schedule

User = get_user_model()


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
        event_dt = timezone.make_aware(datetime(2026, 6, 1, 9, 25), tz)
        result = classify_entrance_against_schedule(squad_id=self.squad.pk, event_dt=event_dt)
        self.assertEqual(result["event_type"], "late")
        self.assertEqual(result["late_minutes"], 25)


# Штраф за опоздание в проде выключен: Положение такого списания не знает.
# Тесты включают его явно — механика остаётся рабочей на случай, когда
# колледж внесёт в документ пункт о турникетах.
class LatePenaltyGateTests(TestCase):
    """Штрафа за опоздание нет: опоздание пишется в событие, рейтинг не трогается.

    HikCentral в Положении не упоминается ни разу: единственное списание —
    за подтверждённый пропуск пары, и только после того, как тьютор
    подтвердил причину. Списывать рейтинг за проход турникета значит
    наказывать правилом, которого колледж не утверждал.
    """

    def test_late_event_is_recorded_without_touching_rating(self):
        squad = Squad.objects.create(code="S9", name="Отряд 9")
        Schedule.objects.create(
            squad=squad,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(10, 30),
            is_active=True,
        )
        user = get_user_model().objects.create_user(
            username="latecomer",
            password="x",
            callsign="late_call",
            squad=squad,
            hik_card_code="CARD-9",
            rating_current=Decimal("300"),
        )
        HikEvent.objects.create(
            event_id="HIK-GATE-1",
            student_code="CARD-9",
            event_time=timezone.make_aware(datetime(2026, 6, 1, 9, 40)),
            event_type="entry",
            door_name="Main",
            raw_data={},
            processed=False,
        )

        process_unprocessed_hik_events()

        user.refresh_from_db()
        self.assertEqual(user.rating_current, Decimal("300"), "рейтинг не трогаем")
        self.assertFalse(RatingLog.objects.filter(user=user).exists())
        self.assertTrue(
            ExternalEvent.objects.filter(user=user, event_type="late").exists(),
            "сам факт опоздания сохраняется: на нём держатся квесты про серии",
        )
