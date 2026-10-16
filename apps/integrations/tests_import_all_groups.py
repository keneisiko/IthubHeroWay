"""Импорт всех групп колледжа одной командой.

Одна группа за вызов означала тридцать вызовов с придуманными руками кодами
и курсами. Здесь проверяется, что код и курс выводятся сами, а группы,
у которых курс не читается, не заводятся наугад.
"""

from __future__ import annotations

from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.models import Role, Squad
from apps.integrations.services.lxp_group_import import (
    course_from_name,
    slug,
    squad_code_for,
)

User = get_user_model()

GROUPS = [
    {"id": "g1", "name": "3ИТР2.9.24", "suborganization": "Нальчик"},
    {"id": "g2", "name": "1ИСП1.9.26", "suborganization": "Нальчик"},
    {"id": "g3", "name": "Группа без курса", "suborganization": "Нальчик"},
]


def students(prefix: str) -> list[dict]:
    return [
        {
            "id": f"{prefix}-s{i}",
            "user": {
                "id": f"{prefix}-u{i}",
                "email": f"{prefix}{i}@nalchik.ithub.ru",
                "firstName": "Имя",
                "lastName": f"Фамилия{i}",
            },
        }
        for i in (1, 2)
    ]


def run(**kwargs) -> str:
    out = StringIO()
    module = "apps.integrations.management.commands.import_lxp_all_groups"
    with (
        mock.patch(f"{module}.list_groups", return_value=GROUPS),
        mock.patch(f"{module}.group_students", side_effect=lambda gid: students(gid)),
    ):
        call_command("import_lxp_all_groups", stdout=out, **kwargs)
    return out.getvalue()


class NamingTests(TestCase):
    def test_course_comes_from_the_first_digit(self):
        self.assertEqual(course_from_name("3ИТР2.9.24"), 3)
        self.assertEqual(course_from_name("1ИСП1.9.26"), 1)

    def test_course_is_not_guessed_without_a_digit(self):
        self.assertEqual(course_from_name("Группа без курса"), 0)
        self.assertEqual(course_from_name(""), 0)

    def test_squad_code_is_latin(self):
        code = squad_code_for({"id": "g1", "name": "3ИТР2.9.24"})

        # Точки из названия группы сохраняются: «3itr2.9.24» узнаётся как
        # «3ИТР2.9.24», а в адресах и в админке точка допустима.
        self.assertEqual(code, "3itr2.9.24")
        self.assertTrue(all(ch.isascii() for ch in code))

    def test_slug_falls_back_when_nothing_transliterates(self):
        self.assertEqual(slug("", fallback="lxp-g9"), "lxp-g9")


class ImportAllGroupsTests(TestCase):
    def test_imports_every_group_with_a_readable_course(self):
        run()

        self.assertEqual(Squad.objects.count(), 2)
        self.assertEqual(
            sorted(Squad.objects.values_list("code", flat=True)), ["1isp1.9.26", "3itr2.9.24"]
        )
        self.assertEqual(User.objects.filter(role=Role.AGENT).count(), 4)

    def test_squad_keeps_the_lxp_group_id(self):
        """Без него у отряда не будет ни расписания, ни отметок посещения."""
        run()

        squad = Squad.objects.get(code="3itr2.9.24")
        self.assertEqual(squad.lxp_group_id, "g1")
        self.assertEqual(squad.course, 3)
        self.assertEqual(squad.name, "3ИТР2.9.24")

    def test_group_without_a_course_is_skipped_and_reported(self):
        output = run()

        self.assertIn("Курс не читается из названия", output)
        self.assertIn("Группа без курса", output)
        self.assertFalse(Squad.objects.filter(name="Группа без курса").exists())

    def test_default_course_picks_up_the_skipped_group(self):
        run(default_course=2)

        squad = Squad.objects.get(lxp_group_id="g3")
        self.assertEqual(squad.course, 2)

    def test_course_filter_narrows_the_import(self):
        run(course=3)

        self.assertEqual(Squad.objects.count(), 1)
        self.assertEqual(Squad.objects.get().course, 3)

    def test_only_filter_narrows_by_name(self):
        run(only="исп")

        self.assertEqual(Squad.objects.count(), 1)
        self.assertEqual(Squad.objects.get().code, "1isp1.9.26")

    def test_dry_run_writes_nothing(self):
        output = run(dry_run=True)

        self.assertEqual(Squad.objects.count(), 0)
        self.assertEqual(User.objects.count(), 0)
        self.assertIn("Будет заведено отрядов: 2", output)

    def test_rerun_does_not_duplicate_students(self):
        run()
        run()

        self.assertEqual(User.objects.filter(role=Role.AGENT).count(), 4)
        self.assertEqual(Squad.objects.count(), 2)

    def test_imported_cards_are_closed_for_login(self):
        run()

        for user in User.objects.filter(role=Role.AGENT):
            with self.subTest(user=user.username):
                self.assertFalse(user.is_active)
                self.assertFalse(user.has_usable_password())

    def test_empty_selection_is_an_error(self):
        with self.assertRaises(CommandError):
            run(only="такой группы нет")

    def test_one_broken_group_does_not_cancel_the_rest(self):
        """Недоступная группа не должна отменять весь импорт."""
        from apps.integrations.services.lxp_graphql_client import LXPRequestError

        module = "apps.integrations.management.commands.import_lxp_all_groups"

        def fetch(group_id):
            if group_id == "g1":
                raise LXPRequestError("портал не ответил")
            return students(group_id)

        out = StringIO()
        with (
            mock.patch(f"{module}.list_groups", return_value=GROUPS),
            mock.patch(f"{module}.group_students", side_effect=fetch),
        ):
            call_command("import_lxp_all_groups", stdout=out)

        output = out.getvalue()
        self.assertIn("Не удалось завести", output)
        self.assertIn("портал не ответил", output)
        self.assertTrue(Squad.objects.filter(code="1isp1.9.26").exists())


class ExistingSquadTests(TestCase):
    """Отряд, заведённый руками, не должен раздваиваться при импорте.

    Пилотный отряд создавали с кодом `itr2-24`, а транслитерация названия
    даёт `3itr2.9.24`. Поиск по одному коду создал бы второй отряд на ту же
    группу LXP, и ночные задачи грузили бы ей расписание и отметки дважды.
    """

    def test_squad_is_found_by_lxp_group_id_not_by_code(self):
        manual = Squad.objects.create(
            code="itr2-24", name="3ИТР2.9.24", course=3, lxp_group_id="g1"
        )

        run(only="3ИТР")

        self.assertEqual(Squad.objects.filter(lxp_group_id="g1").count(), 1)
        self.assertEqual(Squad.objects.get(lxp_group_id="g1").pk, manual.pk)

    def test_existing_squad_keeps_its_code(self):
        """Код мог попасть в закладки и ссылки — не переименовываем."""
        Squad.objects.create(code="itr2-24", name="Старое имя", course=2, lxp_group_id="g1")

        run(only="3ИТР")

        squad = Squad.objects.get(lxp_group_id="g1")
        self.assertEqual(squad.code, "itr2-24")
        self.assertEqual(squad.name, "3ИТР2.9.24", "название приводится к названию группы")
        self.assertEqual(squad.course, 3, "курс приводится к названию группы")

    def test_students_land_in_the_existing_squad(self):
        manual = Squad.objects.create(
            code="itr2-24", name="3ИТР2.9.24", course=3, lxp_group_id="g1"
        )

        run(only="3ИТР")

        self.assertEqual(manual.members.count(), 2)

    def test_squad_without_group_id_is_matched_by_code(self):
        """Старый отряд без связи с LXP подхватывается по коду и получает её."""
        Squad.objects.create(code="3itr2.9.24", name="3ИТР2.9.24", course=3, lxp_group_id="")

        run(only="3ИТР")

        self.assertEqual(Squad.objects.filter(name="3ИТР2.9.24").count(), 1)
        self.assertEqual(Squad.objects.get(code="3itr2.9.24").lxp_group_id, "g1")
