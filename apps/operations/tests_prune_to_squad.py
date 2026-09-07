"""Чистка базы до одного отряда.

Закрытый прогон идёт на одной группе, но удаление 700+ карточек необратимо,
поэтому проверяем границы: кто уходит, кто остаётся и что пробный запуск
действительно ничего не трогает.
"""

from __future__ import annotations

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.models import Role, Squad, User


def make_agent(username: str, squad=None, **kwargs) -> User:
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.ru",
        password="x",
        callsign=f"call_{username}",
        role=kwargs.pop("role", Role.AGENT),
        squad=squad,
        **kwargs,
    )


class PruneToSquadTests(TestCase):
    def setUp(self):
        self.keep = Squad.objects.create(code="itr2-24", name="3ИТР2.9.24", course=3)
        self.other = Squad.objects.create(code="other", name="Чужие", course=1)
        self.mine = make_agent("mine", self.keep)
        self.stranger = make_agent("stranger", self.other)
        self.homeless = make_agent("homeless")

    def test_only_the_chosen_squad_survives(self):
        call_command("prune_to_squad", "itr2-24")

        self.assertEqual(list(User.objects.values_list("username", flat=True)), ["mine"])

    def test_staff_are_never_deleted(self):
        curator = make_agent("curator", self.other, role=Role.CURATOR, is_staff=True)
        root = make_agent("root", None, is_superuser=True)

        call_command("prune_to_squad", "itr2-24")

        self.assertTrue(User.objects.filter(pk=curator.pk).exists())
        self.assertTrue(User.objects.filter(pk=root.pk).exists())

    def test_dry_run_deletes_nobody(self):
        call_command("prune_to_squad", "itr2-24", dry_run=True)

        self.assertEqual(User.objects.count(), 3)

    def test_empty_squads_are_kept_unless_asked(self):
        call_command("prune_to_squad", "itr2-24")

        self.assertTrue(Squad.objects.filter(code="other").exists())

    def test_empty_squads_can_be_dropped(self):
        call_command("prune_to_squad", "itr2-24", drop_empty_squads=True)

        self.assertFalse(Squad.objects.filter(code="other").exists())
        self.assertTrue(Squad.objects.filter(code="itr2-24").exists())

    def test_unknown_squad_is_refused(self):
        with self.assertRaises(CommandError):
            call_command("prune_to_squad", "nope")

    def test_empty_squad_is_refused(self):
        """Иначе опечатка в коде отряда вычистила бы базу целиком."""
        Squad.objects.create(code="empty", name="Пустой", course=3)

        with self.assertRaises(CommandError):
            call_command("prune_to_squad", "empty")
