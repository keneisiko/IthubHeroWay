"""Начисления за «Движ» и годовой цикл рейтинга."""

from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Role
from apps.progress.models import LXPTopicState, RatingLog

User = get_user_model()



def make_agent(username: str, rating: int = 300, unclosed: int = 0) -> User:
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.ru",
        password="x",
        callsign=f"call_{username}",
        role=Role.AGENT,
        rating_current=rating,
        unclosed_ct_count=unclosed,
    )


class StartRatingYearTests(TestCase):
    def test_reset_returns_everyone_to_start_value(self):
        first = make_agent("veteran", rating=880)
        second = make_agent("rookie", rating=305, unclosed=2)
        LXPTopicState.objects.create(user=first, topics={"a": {"closed": True}}, baseline_done=True)

        call_command("start_rating_year", stdout=StringIO())

        first.refresh_from_db()
        second.refresh_from_db()
        # Положение 2.0: сезон начинается с нуля.
        self.assertEqual(first.rating_current, 0)
        self.assertEqual(second.rating_current, 0)
        self.assertEqual(second.unclosed_ct_count, 0)
        self.assertFalse(LXPTopicState.objects.exists(), "программа нового года — новые темы")

    def test_previous_year_total_is_kept_in_log(self):
        user = make_agent("veteran2", rating=760)
        user.coins_balance = 42
        user.save(update_fields=["coins_balance"])

        call_command("start_rating_year", stdout=StringIO())

        log = RatingLog.objects.get(user=user)
        self.assertEqual(log.value_before, 760)
        self.assertEqual(log.value_after, 0)
        self.assertIn("Старт сезона", log.reason)
        # п. 2.5: неиспользованные монеты сгорают и не переносятся.
        self.assertEqual(log.coins_delta, -42)
        user.refresh_from_db()
        self.assertEqual(user.coins_balance, 0)

    def test_dry_run_changes_nothing(self):
        user = make_agent("veteran3", rating=700)

        call_command("start_rating_year", "--dry-run", stdout=StringIO())

        user.refresh_from_db()
        self.assertEqual(user.rating_current, 700)
        self.assertFalse(RatingLog.objects.exists())
