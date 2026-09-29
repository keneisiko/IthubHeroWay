"""Связка проходов Hik со студентами по ФИО.

В портале у людей личные почты, в платформе — учебные из LXP: совпадений
нет вовсе, и 3140 проходов остались без владельцев. Сопоставляем по имени
и запоминаем код человека, чтобы дальше связка шла по нему.
"""

from __future__ import annotations

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.models import Role, Squad, User
from apps.integrations.management.commands.link_hik_persons import name_key
from apps.integrations.models import HikEvent


def make_student(last: str, first: str, squad=None, suffix: str = "") -> User:
    return User.objects.create_user(
        username=f"{last}_{first}{suffix}".lower(),
        email=f"{last}{first}{suffix}@nalchik.ithub.ru".lower(),
        password="x",
        callsign=f"{last}{first}{suffix}",
        role=Role.AGENT,
        last_name=last,
        first_name=first,
        squad=squad,
    )


def make_event(person_name: str, person_code: str = "", person_id: str = "") -> HikEvent:
    return HikEvent.objects.create(
        event_id=f"e-{person_name}-{person_code}-{HikEvent.objects.count()}",
        event_time="2026-09-22T09:10:00+03:00",
        door_name="Вход 1",
        student_code=person_code,
        raw_data={"personName": person_name, "personCode": person_code, "personId": person_id},
    )


class LinkHikPersonsTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="itr2-24", name="3ИТР2.9.24", course=3)
        self.student = make_student("Таов", "Алихан", self.squad)

    def test_name_key_ignores_case_order_and_yo(self):
        self.assertEqual(name_key("Пётр", "Иванов"), name_key("иванов", "петр"))

    def test_code_is_written_to_the_student_card(self):
        make_event("Таов Алихан", person_code="1830160598", person_id="p-1")

        call_command("link_hik_persons", squad="itr2-24", apply=True)

        self.student.refresh_from_db()
        self.assertEqual(self.student.hik_card_code, "1830160598")
        self.assertEqual(self.student.hik_person_id, "p-1")

    def test_dry_run_writes_nothing(self):
        make_event("Таов Алихан", person_code="1830160598")

        call_command("link_hik_persons", squad="itr2-24")

        self.student.refresh_from_db()
        self.assertEqual(self.student.hik_card_code or "", "")

    def test_full_namesakes_are_left_alone(self):
        """Иначе чужие проходы попадут в чей-то рейтинг."""
        twin = make_student("Таов", "Алихан", self.squad, suffix="2")
        make_event("Таов Алихан", person_code="1830160598")

        call_command("link_hik_persons", squad="itr2-24", apply=True)

        self.student.refresh_from_db()
        twin.refresh_from_db()
        self.assertFalse(self.student.hik_card_code)
        self.assertFalse(twin.hik_card_code)

    def test_student_without_passes_is_not_touched(self):
        make_event("Кто-то Другой", person_code="999")

        call_command("link_hik_persons", squad="itr2-24", apply=True)

        self.student.refresh_from_db()
        self.assertFalse(self.student.hik_card_code)

    def test_refuses_without_events(self):
        with self.assertRaises(CommandError):
            call_command("link_hik_persons", squad="itr2-24")
