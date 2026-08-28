"""Начисления за «Движ» и годовой цикл рейтинга."""

from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import Role
from apps.progress.models import LXPTopicState, RatingChangeSource, RatingLog
from apps.progress.services.drive_awards import (
    UnknownDriveCode,
    grant_drive_award,
    grant_drive_award_bulk,
)

User = get_user_model()

DRIVE = {"EVENT_PARTICIPATION": 20, "OLYMPIAD_WIN": 90}


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


@override_settings(RATING_DRIVE=DRIVE)
class DriveAwardTests(TestCase):
    """Блок RATING_DRIVE был описан в регламенте, но не начислялся нигде."""

    def test_award_adds_rating_and_writes_log(self):
        user = make_agent("driver")

        applied = grant_drive_award(user, "EVENT_PARTICIPATION")

        user.refresh_from_db()
        self.assertEqual(applied, 20)
        self.assertEqual(user.rating_current, 320)
        log = RatingLog.objects.get(user=user)
        self.assertEqual(log.source, RatingChangeSource.DRIVE)
        self.assertIn("EVENT_PARTICIPATION", log.reason)

    def test_same_award_twice_in_a_day_is_ignored(self):
        user = make_agent("driver2")

        grant_drive_award(user, "OLYMPIAD_WIN")
        second = grant_drive_award(user, "OLYMPIAD_WIN")

        user.refresh_from_db()
        self.assertEqual(second, 0)
        self.assertEqual(user.rating_current, 390)

    def test_unknown_code_is_rejected(self):
        user = make_agent("driver3")
        with self.assertRaises(UnknownDriveCode):
            grant_drive_award(user, "NOT_A_CODE")

    @override_settings(RATING_LIMITS={"MAX_RATING_WHEN_BLOCKED": 399})
    def test_award_cannot_lift_above_yellow_zone_while_ct_overdue(self):
        """Иначе олимпиадой можно было бы перекрыть просроченные КТ."""
        user = make_agent("driver4", rating=390, unclosed=3)

        grant_drive_award(user, "OLYMPIAD_WIN")

        user.refresh_from_db()
        self.assertEqual(user.rating_current, 399)

    def test_bulk_reports_duplicates(self):
        users = [make_agent(f"bulk{i}") for i in range(3)]
        grant_drive_award(users[0], "EVENT_PARTICIPATION")

        result = grant_drive_award_bulk(users, "EVENT_PARTICIPATION")

        self.assertEqual(result.granted, 2)
        self.assertEqual(result.skipped_duplicate, 1)
        self.assertEqual(result.points_each, 20)


@override_settings(RATING_LIMITS={"DEFAULT_RATING_START": 300})
class StartRatingYearTests(TestCase):
    def test_reset_returns_everyone_to_start_value(self):
        first = make_agent("veteran", rating=880)
        second = make_agent("rookie", rating=305, unclosed=2)
        LXPTopicState.objects.create(user=first, topics={"a": {"closed": True}}, baseline_done=True)

        call_command("start_rating_year", stdout=StringIO())

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.rating_current, 300)
        self.assertEqual(second.rating_current, 300)
        self.assertEqual(second.unclosed_ct_count, 0)
        self.assertFalse(LXPTopicState.objects.exists(), "программа нового года — новые темы")

    def test_previous_year_total_is_kept_in_log(self):
        user = make_agent("veteran2", rating=760)

        call_command("start_rating_year", stdout=StringIO())

        log = RatingLog.objects.get(user=user)
        self.assertEqual(log.value_before, 760)
        self.assertEqual(log.value_after, 300)
        self.assertIn("Старт учебного года", log.reason)

    def test_dry_run_changes_nothing(self):
        user = make_agent("veteran3", rating=700)

        call_command("start_rating_year", "--dry-run", stdout=StringIO())

        user.refresh_from_db()
        self.assertEqual(user.rating_current, 700)
        self.assertFalse(RatingLog.objects.exists())
