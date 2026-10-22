from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.callsigns import default_callsign, is_auto_callsign
from apps.accounts.models import Role, User


def make(username, callsign, first="Наима", last="Дударкаева"):
    return User.objects.create_user(
        username=username, callsign=callsign, password=None, role=Role.AGENT,
        first_name=first, last_name=last,
    )


class DefaultCallsignTests(TestCase):
    def test_name_and_initial(self):
        self.assertEqual(default_callsign("Наима", "Дударкаева", fallback="x"), "Наима Д.")

    def test_taken_gets_number(self):
        make("a", "Наима Д.")
        make("b", "Наима Д. 2")
        self.assertEqual(default_callsign("Наима", "Дударкаева", fallback="x"), "Наима Д. 3")

    def test_fallback_without_names(self):
        self.assertEqual(default_callsign("", "", fallback="student-1"), "student-1")


class AutoCallsignTests(TestCase):
    def test_import_callsigns_are_auto(self):
        self.assertTrue(is_auto_callsign(make("dudarkaevann25-a3b18c2c", "dudarkaevann25-a3b18c2c")))
        self.assertTrue(is_auto_callsign(make("dorogovaam24_4e9bd5ea", "lxp_4e9bd5ea-fe4")))

    def test_own_callsign_is_kept(self):
        self.assertFalse(is_auto_callsign(make("kazanovzz23-81a5bfba", "keneisiko")))


class ShortenCommandTests(TestCase):
    def test_dry_run_changes_nothing_and_apply_renames_only_auto(self):
        auto = make("dudarkaevann25-a3b18c2c", "dudarkaevann25-a3b18c2c")
        own = make("kazanovzz23-81a5bfba", "keneisiko", first="Заракуш", last="Казанов")

        call_command("shorten_callsigns", stdout=StringIO())
        auto.refresh_from_db()
        self.assertEqual(auto.callsign, "dudarkaevann25-a3b18c2c")

        call_command("shorten_callsigns", "--apply", stdout=StringIO())
        auto.refresh_from_db()
        own.refresh_from_db()
        self.assertEqual(auto.callsign, "Наима Д.")
        self.assertEqual(own.callsign, "keneisiko")
