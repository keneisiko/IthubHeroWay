"""Импорт учебной группы LXP в отряд.

Общий импорт студентов заводит карточки без групп и курсов, поэтому
проверяем главное: состав группы попадает в отряд, уже заведённые карточки
не дублируются, а вход остаётся закрытым до привязки Telegram.
"""

from __future__ import annotations

from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.models import Role, Squad, User

GROUP = [
    {"id": "s1", "user": {"id": "u1", "email": "Ivanov@nalchik.ithub.ru", "firstName": "Иван", "lastName": "Иванов"}},
    {"id": "s2", "user": {"id": "u2", "email": "petrov@nalchik.ithub.ru", "firstName": "Пётр", "lastName": "Петров"}},
]


def run(**kwargs):
    with mock.patch("apps.integrations.management.commands.import_lxp_group.group_students", return_value=GROUP):
        call_command("import_lxp_group", **kwargs)


class ImportGroupTests(TestCase):
    def test_group_becomes_a_squad_with_its_students(self):
        run(group_id="g1", squad_code="pi-31", squad_name="ПИ-31", course=3)

        squad = Squad.objects.get(code="pi-31")
        self.assertEqual((squad.name, squad.course), ("ПИ-31", 3))
        self.assertEqual(squad.members.count(), 2)

    def test_imported_students_cannot_log_in_until_telegram_is_linked(self):
        run(group_id="g1", squad_code="pi-31", course=3)

        for user in User.objects.filter(squad__code="pi-31"):
            self.assertFalse(user.is_active)
            self.assertFalse(user.has_usable_password())
            self.assertEqual(user.role, Role.AGENT)

    def test_existing_card_is_reused_not_duplicated(self):
        existing = User.objects.create_user(
            username="ivanov_old",
            email="ivanov@nalchik.ithub.ru",
            password="x",
            callsign="Старый",
            lxp_user_id="u1",
        )

        run(group_id="g1", squad_code="pi-31", course=3)

        existing.refresh_from_db()
        self.assertEqual(existing.squad.code, "pi-31")
        self.assertEqual(User.objects.filter(lxp_user_id="u1").count(), 1)

    def test_repeated_import_does_not_multiply_the_squad(self):
        run(group_id="g1", squad_code="pi-31", course=3)
        run(group_id="g1", squad_code="pi-31", course=3)

        self.assertEqual(Squad.objects.filter(code="pi-31").count(), 1)
        self.assertEqual(User.objects.filter(squad__code="pi-31").count(), 2)

    def test_course_outside_the_college_range_is_rejected(self):
        with self.assertRaises(CommandError):
            run(group_id="g1", squad_code="pi-31", course=9)

    def test_dry_run_writes_nothing(self):
        run(group_id="g1", squad_code="pi-31", course=3, dry_run=True)

        self.assertFalse(Squad.objects.filter(code="pi-31").exists())
        self.assertFalse(User.objects.filter(lxp_user_id="u1").exists())
