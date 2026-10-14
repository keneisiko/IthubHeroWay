"""Начисления по разделам 4-7 Положения и списания по разделу 9.

Проверяются именно те правила, которые Положение формулирует словами и
которые легко потерять в коде: одна наивысшая роль на мероприятие, доплата
разницы при победе после участия, запрет двойной оплаты одной работы,
пропорция за неполную неделю и потолок списания за день.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.models import Role
from apps.progress.models import (
    LessonAttendance,
    LessonAttendanceStatus,
    PolozhenieAward,
    RatingLog,
    StudentRoleAssignment,
    StudentRoleKind,
)
from apps.progress.services.polozhenie_awards import (
    UnknownTariff,
    absence_penalty_for_day,
    accrue_roles_for_user,
    award_event,
    award_olympiad,
    award_project,
    run_weekly_roles,
)

User = get_user_model()

WEEK_MONDAY = date(2026, 10, 19)
WEEK_FRIDAY = date(2026, 10, 23)
SEASON = {"SEASON_START_DATE": "2026-10-19", "DECIMAL_PLACES": 2}


def make_student(username: str = "student") -> User:
    return User.objects.create_user(
        username=username,
        email=f"{username}@nalchik.ithub.ru",
        password="x",
        callsign=f"call_{username}",
        role=Role.AGENT,
    )


@override_settings(POLOZHENIE_PERIOD=SEASON)
class EventAwardTests(TestCase):
    """Раздел 5: мероприятия."""

    def setUp(self):
        self.user = make_student()

    def test_tariff_depends_on_level_and_role(self):
        outcome = award_event(
            self.user, activity_key="forum-1", level="region", role="speaker", title="Форум"
        )

        self.assertTrue(outcome.granted)
        self.assertEqual(outcome.rating, Decimal("12.00"))
        self.assertEqual(outcome.coins, Decimal("40.00"))

    def test_same_event_is_not_paid_twice(self):
        award_event(self.user, activity_key="forum-1", level="city", role="listener")
        repeat = award_event(self.user, activity_key="forum-1", level="city", role="listener")

        self.assertFalse(repeat.granted)
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("2.00"))

    def test_higher_role_is_paid_as_difference(self):
        """Пункт 5.2: применяется одна наиболее высокая подтверждённая роль."""
        award_event(self.user, activity_key="forum-1", level="region", role="listener")
        upgrade = award_event(self.user, activity_key="forum-1", level="region", role="speaker")

        self.assertTrue(upgrade.granted)
        # Спикер региона 12/40, слушатель региона 3/8: доплата 9 и 32.
        self.assertEqual(upgrade.rating, Decimal("9.00"))
        self.assertEqual(upgrade.coins, Decimal("32.00"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("12.00"))

    def test_lower_role_adds_nothing(self):
        award_event(self.user, activity_key="forum-1", level="region", role="speaker")
        downgrade = award_event(self.user, activity_key="forum-1", level="region", role="listener")

        self.assertFalse(downgrade.granted)
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("12.00"))

    def test_unknown_level_is_rejected(self):
        with self.assertRaises(UnknownTariff):
            award_event(self.user, activity_key="x", level="galaxy", role="speaker")

    def test_award_row_keeps_confirmation(self):
        staff = User.objects.create_user(
            username="kumykova", password="x", callsign="kum", role=Role.HQ
        )
        award_event(
            self.user,
            activity_key="forum-2",
            level="federal",
            role="volunteer",
            happened_on=WEEK_FRIDAY,
            confirmed_by=staff,
        )

        row = PolozhenieAward.objects.get(user=self.user, activity_key="forum-2")
        self.assertEqual(row.confirmed_by, staff)
        self.assertEqual(row.happened_on, WEEK_FRIDAY)
        log = RatingLog.objects.get(user=self.user, source_id="event:forum-2")
        self.assertEqual(log.confirmed_by, staff)


@override_settings(POLOZHENIE_PERIOD=SEASON)
class OlympiadAwardTests(TestCase):
    """Раздел 6: олимпиады."""

    def setUp(self):
        self.user = make_student()

    def test_win_after_participation_pays_difference(self):
        """Пункт 6.3: если участие учтено, начисляется разница."""
        award_olympiad(self.user, activity_key="olymp-1", level="region", result="participation")
        win = award_olympiad(self.user, activity_key="olymp-1", level="region", result="win")

        # Победа в регионе 15/50, участие 3/8: доплата 12 и 42.
        self.assertEqual(win.rating, Decimal("12.00"))
        self.assertEqual(win.coins, Decimal("42.00"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("15.00"))

    def test_win_without_prior_participation_pays_full(self):
        win = award_olympiad(self.user, activity_key="olymp-2", level="federal", result="win")

        self.assertEqual(win.rating, Decimal("25.00"))
        self.assertEqual(win.coins, Decimal("80.00"))

    def test_participation_after_win_adds_nothing(self):
        award_olympiad(self.user, activity_key="olymp-3", level="college", result="win")
        again = award_olympiad(
            self.user, activity_key="olymp-3", level="college", result="participation"
        )

        self.assertFalse(again.granted)


@override_settings(POLOZHENIE_PERIOD=SEASON)
class ProjectAwardTests(TestCase):
    """Раздел 7: проекты бизнес-инкубатора."""

    def setUp(self):
        self.user = make_student()

    def test_tariff_by_result(self):
        outcome = award_project(self.user, activity_key="inc-1", result="project")

        self.assertEqual(outcome.rating, Decimal("25.00"))
        self.assertEqual(outcome.coins, Decimal("100.00"))

    def test_one_work_is_not_paid_as_task_and_stage(self):
        """Пункт 7.3: одна работа не оплачивается повторно."""
        award_project(self.user, activity_key="inc-2", result="task")
        again = award_project(self.user, activity_key="inc-2", result="stage")

        self.assertFalse(again.granted)
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("5.00"))

    def test_final_award_adds_to_stages_under_its_own_key(self):
        """Пункт 7.3: финальная награда может добавляться к наградам за этапы."""
        award_project(self.user, activity_key="inc-3-stage-1", result="stage")
        award_project(self.user, activity_key="inc-3-final", result="project")

        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("35.00"))

    def test_unknown_result_is_rejected(self):
        with self.assertRaises(UnknownTariff):
            award_project(self.user, activity_key="inc-4", result="whatever")


@override_settings(POLOZHENIE_PERIOD=SEASON)
class StudentRoleTests(TestCase):
    """Раздел 4: регулярные роли."""

    def setUp(self):
        self.user = make_student()

    def test_full_week_pays_full_tariff(self):
        StudentRoleAssignment.objects.create(
            user=self.user, kind=StudentRoleKind.TECH, started_on=WEEK_MONDAY
        )

        outcome = accrue_roles_for_user(self.user, WEEK_MONDAY)

        self.assertEqual(outcome.rating, Decimal("9.00"))
        self.assertEqual(outcome.coins, Decimal("30.00"))

    def test_partial_week_is_proportional(self):
        """Пункт 4.2: за неполную неделю — пропорционально учебным дням."""
        StudentRoleAssignment.objects.create(
            user=self.user,
            kind=StudentRoleKind.TECH,
            started_on=WEEK_MONDAY,
            ended_on=date(2026, 10, 21),
        )

        outcome = accrue_roles_for_user(self.user, WEEK_MONDAY)

        # Три учебных дня из пяти: 9 × 0,6 = 5,40 и 30 × 0,6 = 18,00.
        self.assertEqual(outcome.rating, Decimal("5.40"))
        self.assertEqual(outcome.coins, Decimal("18.00"))

    def test_combined_roles_are_summed(self):
        """Пункт 4.3: куратор и преподаватель — 12 рейтинга и 45 монет."""
        StudentRoleAssignment.objects.create(
            user=self.user, kind=StudentRoleKind.CURATOR, started_on=WEEK_MONDAY
        )
        StudentRoleAssignment.objects.create(
            user=self.user, kind=StudentRoleKind.TEACHER, started_on=WEEK_MONDAY
        )

        outcome = accrue_roles_for_user(self.user, WEEK_MONDAY)

        self.assertEqual(outcome.rating, Decimal("12.00"))
        self.assertEqual(outcome.coins, Decimal("45.00"))

    def test_role_is_not_paid_twice_for_the_same_week(self):
        StudentRoleAssignment.objects.create(
            user=self.user, kind=StudentRoleKind.CLUB_LEAD, started_on=WEEK_MONDAY
        )

        accrue_roles_for_user(self.user, WEEK_MONDAY)
        repeat = accrue_roles_for_user(self.user, WEEK_MONDAY)

        self.assertFalse(repeat.granted)
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("4.00"))

    def test_ended_role_stops_paying(self):
        StudentRoleAssignment.objects.create(
            user=self.user,
            kind=StudentRoleKind.CLUB_LEAD,
            started_on=WEEK_MONDAY,
            ended_on=date(2026, 10, 23),
        )

        next_week = accrue_roles_for_user(self.user, date(2026, 10, 26))

        self.assertFalse(next_week.granted)

    def test_weekend_only_role_pays_nothing(self):
        """Суббота и воскресенье в учебные дни не входят."""
        StudentRoleAssignment.objects.create(
            user=self.user,
            kind=StudentRoleKind.CLUB_LEAD,
            started_on=date(2026, 10, 24),
            ended_on=date(2026, 10, 25),
        )

        outcome = accrue_roles_for_user(self.user, WEEK_MONDAY)

        self.assertFalse(outcome.granted)

    def test_run_covers_only_students_with_roles(self):
        make_student("without_role")
        StudentRoleAssignment.objects.create(
            user=self.user, kind=StudentRoleKind.GROUP_LEAD, started_on=WEEK_MONDAY
        )

        result = run_weekly_roles(WEEK_MONDAY)

        self.assertEqual(result["paid"], 1)
        self.assertEqual(result["rating"], Decimal("2.00"))


@override_settings(POLOZHENIE_PERIOD=SEASON)
class AbsencePenaltyTests(TestCase):
    """Раздел 9: списания за пропуски."""

    def setUp(self):
        self.user = make_student()
        self.user.rating_current = Decimal("50.00")
        self.user.coins_balance = Decimal("20.00")
        self.user.save(update_fields=["rating_current", "coins_balance"])

    def _miss(self, count: int, day: date = WEEK_MONDAY) -> None:
        for i in range(count):
            LessonAttendance.objects.create(
                user=self.user,
                lxp_class_id=f"{day.isoformat()}-{i}",
                lesson_date=day,
                status=LessonAttendanceStatus.MISSED,
            )

    def test_one_point_per_lesson(self):
        self._miss(2)

        outcome = absence_penalty_for_day(self.user, WEEK_MONDAY)

        self.assertEqual(outcome.rating, Decimal("-2.00"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("48.00"))

    def test_daily_cap_is_four(self):
        """Пункт 9.1: максимум 4 за учебный день, дополнительного штрафа нет."""
        self._miss(6)

        outcome = absence_penalty_for_day(self.user, WEEK_MONDAY)

        self.assertEqual(outcome.rating, Decimal("-4.00"))

    def test_coins_are_not_taken(self):
        """Пункт 9.4: штрафы затрагивают только рейтинг."""
        self._miss(3)

        absence_penalty_for_day(self.user, WEEK_MONDAY)

        self.user.refresh_from_db()
        self.assertEqual(self.user.coins_balance, Decimal("20.00"))

    def test_same_day_is_not_charged_twice(self):
        self._miss(2)
        absence_penalty_for_day(self.user, WEEK_MONDAY)
        repeat = absence_penalty_for_day(self.user, WEEK_MONDAY)

        self.assertFalse(repeat.granted)
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("48.00"))

    def test_rating_never_goes_below_zero(self):
        """Пункт 2.4: рейтинг не может быть ниже нуля."""
        self.user.rating_current = Decimal("1.00")
        self.user.save(update_fields=["rating_current"])
        self._miss(4)

        absence_penalty_for_day(self.user, WEEK_MONDAY)

        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("0.00"))

    def test_day_without_misses_charges_nothing(self):
        outcome = absence_penalty_for_day(self.user, WEEK_MONDAY)

        self.assertFalse(outcome.granted)
        self.assertEqual(outcome.note, "no_missed_lessons")


@override_settings(POLOZHENIE_PERIOD=SEASON)
class BulkTariffTests(TestCase):
    """Пакетное начисление списком участников (п. 5.1, 7.2)."""

    def setUp(self):
        self.first = make_student("first")
        self.second = make_student("second")

    def test_choices_cover_all_tariffs(self):
        from apps.progress.services.polozhenie_awards import tariff_choices

        codes = [code for code, _ in tariff_choices()]

        # 12 комбинаций мероприятий, 8 олимпиад, 3 проекта.
        self.assertEqual(len(codes), 23)
        self.assertIn("event:region:speaker", codes)
        self.assertIn("olympiad:federal:win", codes)
        self.assertIn("project::stage", codes)

    def test_bulk_award_pays_everyone_once(self):
        from apps.progress.services.polozhenie_awards import award_bulk_by_tariff_code

        result = award_bulk_by_tariff_code(
            [self.first, self.second],
            "event:city:volunteer",
            activity_key="den-otkrytyh-dverey:2026-10-19",
            title="День открытых дверей",
        )

        self.assertEqual(result["granted"], 2)
        self.assertEqual(result["rating"], Decimal("14.00"))
        self.assertEqual(result["coins"], Decimal("40.00"))

    def test_repeating_the_same_activity_skips(self):
        from apps.progress.services.polozhenie_awards import award_bulk_by_tariff_code

        kwargs = {"activity_key": "forum:2026-10-19", "title": "Форум"}
        award_bulk_by_tariff_code([self.first], "event:college:listener", **kwargs)
        repeat = award_bulk_by_tariff_code([self.first], "event:college:listener", **kwargs)

        self.assertEqual(repeat["granted"], 0)
        self.assertEqual(repeat["skipped"], 1)

    def test_unknown_code_is_rejected(self):
        from apps.progress.services.polozhenie_awards import parse_tariff_code

        with self.assertRaises(UnknownTariff):
            parse_tariff_code("drive:EVENT_PARTICIPATION")
