"""Учётные записи персонала по пункту 11.2 Положения."""

from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.models import Role
from apps.accounts.staff_roster import STAFF

User = get_user_model()


def run(*args) -> str:
    out = StringIO()
    call_command("sync_staff", *args, stdout=out)
    return out.getvalue()


class SyncStaffTests(TestCase):
    def test_creates_everyone_from_the_roster(self):
        run()

        self.assertEqual(User.objects.filter(is_staff=True).count(), len(STAFF))

    def test_only_service_owner_is_superuser(self):
        """Лишний суперпользователь — лишний способ потерять данные."""
        run()

        supers = list(User.objects.filter(is_superuser=True).values_list("username", flat=True))
        self.assertEqual(supers, ["sarakhov"])

    def test_roles_match_what_each_confirms(self):
        run()

        self.assertEqual(User.objects.get(username="kumykova").role, Role.HQ)
        self.assertEqual(User.objects.get(username="dygova").role, Role.HQ)
        self.assertEqual(User.objects.get(username="kankulova").role, Role.TUTOR)
        self.assertEqual(User.objects.get(username="ulbashev").role, Role.ADMIN)

    def test_passwords_are_shown_once_and_usable(self):
        output = run()

        self.assertIn("Пароли показываются один раз", output)
        line = next(ln for ln in output.splitlines() if ln.startswith("dygova"))
        password = line.split()[1]
        user = User.objects.get(username="dygova")
        self.assertTrue(user.check_password(password))

    def test_rerun_creates_nobody_and_keeps_password(self):
        first = run()
        password = next(ln for ln in first.splitlines() if ln.startswith("dygova")).split()[1]

        second = run()

        self.assertIn("Создано: 0", second)
        self.assertTrue(User.objects.get(username="dygova").check_password(password))

    def test_role_drift_is_reported_but_not_changed(self):
        run()
        User.objects.filter(username="dygova").update(role=Role.AGENT)

        output = run()

        self.assertIn("расходится с роспиcью", output)
        self.assertEqual(User.objects.get(username="dygova").role, Role.AGENT)

    def test_update_existing_restores_the_roster(self):
        run()
        User.objects.filter(username="dygova").update(
            role=Role.AGENT, is_staff=False, is_superuser=True
        )

        run("--update-existing")

        user = User.objects.get(username="dygova")
        self.assertEqual(user.role, Role.HQ)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_dry_run_writes_nothing(self):
        output = run("--dry-run")

        self.assertEqual(User.objects.filter(is_staff=True).count(), 0)
        self.assertIn("будет создан", output)

    def test_dry_run_warns_about_guessed_emails(self):
        output = run("--dry-run")

        self.assertIn("не подтверждены", output)

    def test_reset_password_issues_a_new_one(self):
        run()
        old = User.objects.get(username="mamaeva").password

        output = run("--reset-password", "mamaeva")

        self.assertIn("Новый пароль для mamaeva", output)
        self.assertNotEqual(User.objects.get(username="mamaeva").password, old)

    def test_reset_password_refuses_outsiders(self):
        User.objects.create_user(username="someone", password="x", callsign="someone")

        with self.assertRaises(CommandError):
            call_command("sync_staff", "--reset-password", "someone", stdout=StringIO())

    def test_staff_callsigns_do_not_collide_with_students(self):
        run()

        callsigns = list(User.objects.filter(is_staff=True).values_list("callsign", flat=True))
        self.assertEqual(len(callsigns), len(set(callsigns)))
        self.assertTrue(all(c.startswith("staff-") for c in callsigns))
