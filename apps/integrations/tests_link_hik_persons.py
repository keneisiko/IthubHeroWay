"""Связка проходов Hik со студентами по ФИО.

В портале у людей личные почты, в платформе — учебные из LXP: совпадений
нет вовсе, и 3140 проходов остались без владельцев. Сопоставляем по имени
и запоминаем код человека, чтобы дальше связка шла по нему.
"""

from __future__ import annotations

from unittest import mock

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


class ReprocessHikEventsTests(TestCase):
    """Разбор сохранённых проходов после проставления кодов.

    Проходы приходят раньше, чем известно, кому они принадлежат: связка
    делается кодами позже, и уже сохранённые события нужно разобрать заново.
    """

    def setUp(self):
        self.squad = Squad.objects.create(code="itr2-24", name="3ИТР2.9.24", course=3)
        self.student = make_student("Таов", "Алихан", self.squad)

    def test_events_are_reset_and_processed_again(self):
        event = make_event("Таов Алихан", person_code="1830160598")
        event.processed = True
        event.save(update_fields=["processed"])
        self.student.hik_card_code = "1830160598"
        self.student.save(update_fields=["hik_card_code"])

        call_command("reprocess_hik_events")

        event.refresh_from_db()
        self.assertTrue(event.processed)

    def test_only_unmatched_keeps_linked_events_alone(self):
        linked = make_event("Таов Алихан", person_code="1830160598")
        linked.processed = True
        linked.save(update_fields=["processed"])
        orphan = make_event("Никто Ничей", person_code="")
        orphan.processed = True
        orphan.save(update_fields=["processed"])

        with mock.patch(
            "apps.integrations.management.commands.reprocess_hik_events."
            "process_unprocessed_hik_events",
            return_value=(0, 0, 0),
        ):
            call_command("reprocess_hik_events", only_unmatched=True)

        linked.refresh_from_db()
        orphan.refresh_from_db()
        self.assertTrue(linked.processed)
        self.assertFalse(orphan.processed)
