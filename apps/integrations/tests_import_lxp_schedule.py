"""Расписание отряда из занятий LXP.

Без него дедлайн «Утреннего чек-ина» был общим — 10:00 для всех. У группы
3ИТР2.9.24 первая пара в понедельник в 12:50, и квест засчитывал опоздание
тем, кто пришёл вовремя.
"""

from __future__ import annotations

from datetime import time
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.models import Squad
from apps.integrations.management.commands.import_lxp_schedule import parse_moment
from apps.schedule.models import Schedule

# Время в LXP приходит в UTC; платформа живёт по Москве (+03:00).
CLASSES = [
    {
        "id": "c1",
        "from": "2026-09-21T09:50:00.000Z",
        "to": "2026-09-21T11:20:00.000Z",
        "discipline": {"name": "Английский язык"},
    },
    {
        "id": "c2",
        "from": "2026-09-21T11:30:00.000Z",
        "to": "2026-09-21T13:00:00.000Z",
        "discipline": {"name": "Разработка Backend"},
    },
    {
        # Та же пара следующей недели: в расписании должна остаться одна.
        "id": "c3",
        "from": "2026-09-28T09:50:00.000Z",
        "to": "2026-09-28T11:20:00.000Z",
        "discipline": {"name": "Английский язык"},
    },
    {
        "id": "c4",
        "from": "2026-09-22T06:00:00.000Z",
        "to": "2026-09-22T07:30:00.000Z",
        "discipline": {"name": "Node.js"},
    },
]


def run(**kwargs):
    with mock.patch(
        "apps.integrations.management.commands.import_lxp_schedule.group_classes",
        return_value=CLASSES,
    ):
        call_command("import_lxp_schedule", group_id="g1", squad_code="itr2-24", **kwargs)


class ImportScheduleTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="itr2-24", name="3ИТР2.9.24", course=3)

    def test_utc_time_becomes_local(self):
        moment = parse_moment("2026-09-21T09:50:00.000Z")

        self.assertEqual(moment.time(), time(12, 50))

    def test_weekly_repeats_collapse_into_one_slot(self):
        run()

        monday = Schedule.objects.filter(squad=self.squad, day_of_week=0)
        self.assertEqual(monday.count(), 2)
        self.assertEqual(Schedule.objects.count(), 3)

    def test_first_pair_of_monday_is_not_ten_in_the_morning(self):
        """Ровно тот случай, ради которого расписание и нужно."""
        run()

        first = Schedule.objects.filter(squad=self.squad, day_of_week=0).order_by("start_time").first()
        self.assertEqual(first.start_time, time(12, 50))

    def test_discipline_is_kept(self):
        run()

        slot = Schedule.objects.get(squad=self.squad, day_of_week=1)
        self.assertEqual(slot.discipline, "Node.js")
        self.assertEqual(slot.start_time, time(9, 0))

    def test_dry_run_writes_nothing(self):
        run(dry_run=True)

        self.assertEqual(Schedule.objects.count(), 0)

    def test_repeat_import_does_not_multiply_slots(self):
        run()
        run()

        self.assertEqual(Schedule.objects.count(), 3)

    def test_unknown_squad_is_refused(self):
        with self.assertRaises(CommandError):
            call_command("import_lxp_schedule", group_id="g1", squad_code="nope")

    def test_empty_answer_is_refused(self):
        with mock.patch(
            "apps.integrations.management.commands.import_lxp_schedule.group_classes",
            return_value=[],
        ):
            with self.assertRaises(CommandError):
                call_command("import_lxp_schedule", group_id="g1", squad_code="itr2-24")
