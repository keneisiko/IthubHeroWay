"""Опоздание — это первый вход за день, а не каждый проход.

Две недели пилота: 114 опозданий на 8 обычных проходов, штрафы «Опоздание
233 мин». Опозданием считался любой проход после начала первой пары —
возвращение с обеда и приход на вечернюю пару в том числе.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Role, Squad
from apps.integrations.models import ExternalEvent, HikEvent
from apps.integrations.services.hik_attendance_processor import process_unprocessed_hik_events
from apps.schedule.models import Schedule
from apps.schedule.services import classify_entrance_against_schedule

User = get_user_model()
TUESDAY = datetime(2026, 10, 6)


def moment(hour: int, minute: int):
    return timezone.make_aware(TUESDAY.replace(hour=hour, minute=minute))


class GracePeriodTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="itr2-24", name="3ИТР2.9.24", course=3)
        Schedule.objects.create(
            squad=self.squad,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(10, 30),
            is_active=True,
        )

    def classify(self, hour: int, minute: int):
        return classify_entrance_against_schedule(squad_id=self.squad.pk, event_dt=moment(hour, minute))

    def test_arrival_exactly_at_the_bell_is_not_late(self):
        self.assertEqual(self.classify(9, 0)["event_type"], "access")

    @override_settings(HIK_LATE_GRACE_MINUTES=10)
    def test_arrival_within_grace_is_not_late(self):
        self.assertEqual(self.classify(9, 8)["event_type"], "access")

    @override_settings(HIK_LATE_GRACE_MINUTES=10)
    def test_real_lateness_is_still_counted(self):
        result = self.classify(9, 25)

        self.assertEqual(result["event_type"], "late")
        self.assertEqual(result["late_minutes"], 25)


class FirstEntryOfDayTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="itr2-24", name="3ИТР2.9.24", course=3)
        for weekday in (1, 2):
            Schedule.objects.create(
                squad=self.squad,
                day_of_week=weekday,
                start_time=time(9, 0),
                end_time=time(16, 0),
                is_active=True,
            )
        self.user = User.objects.create_user(
            username="agent",
            email="a@test.ru",
            password="x",
            callsign="Агент",
            squad=self.squad,
            role=Role.AGENT,
            hik_card_code="1830160598",
        )

    def make_pass(self, hour: int, minute: int, *, entry: bool = True, suffix: str = ""):
        return HikEvent.objects.create(
            event_id=f"e-{hour}-{minute}{suffix}",
            event_time=moment(hour, minute),
            door_name="Вход 1",
            student_code="1830160598",
            raw_data={"direction": 1 if entry else 2, "personCode": "1830160598"},
        )

    def types(self):
        return list(
            ExternalEvent.objects.filter(user=self.user).order_by("id").values_list("event_type", flat=True)
        )

    def test_return_after_lunch_is_not_a_second_lateness(self):
        self.make_pass(8, 55)
        self.make_pass(12, 48, suffix="-lunch")

        process_unprocessed_hik_events()

        self.assertEqual(self.types(), ["access", "access"])

    def test_late_first_entry_is_marked_once(self):
        self.make_pass(9, 40)
        self.make_pass(13, 10, suffix="-again")

        process_unprocessed_hik_events()

        self.assertEqual(self.types(), ["late", "access"])

    def test_exit_does_not_become_lateness(self):
        self.make_pass(14, 30, entry=False)

        process_unprocessed_hik_events()

        self.assertEqual(self.types(), ["access"])

    def test_next_day_is_judged_on_its_own(self):
        self.make_pass(9, 40)
        HikEvent.objects.create(
            event_id="e-next-day",
            event_time=moment(9, 40) + timedelta(days=1),
            door_name="Вход 1",
            student_code="1830160598",
            raw_data={"direction": 1},
        )

        process_unprocessed_hik_events()

        self.assertEqual(self.types(), ["late", "late"])
