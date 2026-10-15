"""Недельные учебные начисления по разделу 3 Положения.

Формула Б = 17 × К / 100 + 13 × П / 100 проверяется на тех примерах, которые
приведены в самом Положении (п. 3.5), плюс отдельно каждое правило, которое
легко потерять при правке: отложенные компоненты, неоплачиваемые недели до
старта сезона и запрет на повторную оплату периода.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.models import Role
from apps.integrations.models import LXPSnapshot
from apps.progress.models import LessonAttendance, LessonAttendanceStatus, RatingLog
from apps.progress.services.polozhenie_academic import (
    accrue_week_for_user,
    ct_percent_from_snapshot,
    run_weekly_accrual,
)
from apps.progress.services.polozhenie_period import period_key, week_start

User = get_user_model()

# Понедельник недели, на которую приходится старт сезона 19.10.2026.
WEEK_MONDAY = date(2026, 10, 19)
SEASON = {"SEASON_START_DATE": "2026-10-19", "DECIMAL_PLACES": 2}


def make_student(username: str = "student", lxp_uid: str = "lxp-1") -> User:
    return User.objects.create_user(
        username=username,
        email=f"{username}@nalchik.ithub.ru",
        password="x",
        callsign=f"call_{username}",
        role=Role.AGENT,
        lxp_user_id=lxp_uid,
    )


def snapshot_with(statuses: dict[str, list[str]], snap_date: date) -> LXPSnapshot:
    return LXPSnapshot.objects.create(
        date=snap_date,
        data={
            "meta": {"partial": False},
            "control_points": {
                "ok": True,
                "data": {
                    uid: {
                        "disc-a": {
                            "topics": [
                                {"status": status, "topic": {"id": f"t{i}"}}
                                for i, status in enumerate(rows)
                            ]
                        }
                    }
                    for uid, rows in statuses.items()
                },
            },
        },
    )


def add_lessons(user: User, day: date, *, total: int, missed: int) -> None:
    for i in range(total):
        LessonAttendance.objects.create(
            user=user,
            lxp_class_id=f"{day.isoformat()}-{i}",
            lesson_date=day,
            status=(
                LessonAttendanceStatus.MISSED if i < missed else LessonAttendanceStatus.PRESENT
            ),
        )


@override_settings(
    POLOZHENIE_PERIOD=SEASON,
    POLOZHENIE_CT_SCOPE="decided",
    POLOZHENIE_CT_MIN_ACTUAL=1,
)
class CtPercentTests(TestCase):
    """Пункт 3.1: средний процент актуальных КТ, несданная актуальная — 0%."""

    def test_passed_and_open_topics_give_share(self):
        percent, actual, passed = ct_percent_from_snapshot(
            {"d1": {"topics": [{"status": "PASSED"}, {"status": "IN_PROGRESS"}]}}
        )

        self.assertEqual((actual, passed), (2, 1))
        self.assertEqual(percent, Decimal("50.00"))

    def test_future_topics_are_excluded(self):
        """Будущая КТ не входит в расчёт и не тянет успеваемость вниз."""
        percent, actual, _ = ct_percent_from_snapshot(
            {"d1": {"topics": [{"status": "PASSED"}, {"status": "NOT_STARTED"}]}}
        )

        self.assertEqual(actual, 1)
        self.assertEqual(percent, Decimal("100.00"))

    def test_no_actual_topics_means_no_basis(self):
        """Пункт 3.6: нет актуальных КТ — компонент не начисляется вовсе."""
        percent, actual, _ = ct_percent_from_snapshot({"d1": {"topics": [{"status": "LOCKED"}]}})

        self.assertEqual(actual, 0)
        self.assertIsNone(percent)

    def test_empty_status_is_not_counted_as_unpassed(self):
        """Пробел в выгрузке — это не несданная КТ, а отсутствие данных."""
        percent, actual, _ = ct_percent_from_snapshot({"d1": {"topics": [{"status": ""}]}})

        self.assertEqual(actual, 0)
        self.assertIsNone(percent)


@override_settings(
    POLOZHENIE_PERIOD=SEASON,
    POLOZHENIE_ACADEMIC={"CT_WEEKLY_MAX": Decimal("17"), "ATTENDANCE_WEEKLY_MAX": Decimal("13")},
    POLOZHENIE_CT_SCOPE="decided",
    POLOZHENIE_CT_MIN_ACTUAL=1,
)
class WeeklyAccrualTests(TestCase):
    def setUp(self):
        self.user = make_student()

    def test_example_from_polozhenie(self):
        """Пункт 3.5: КТ 80% и посещаемость 80% дают 24 балла и 24 монеты."""
        # Восемь сданных из десяти актуальных — те же 80%.
        snapshot_with({"lxp-1": ["PASSED"] * 8 + ["IN_PROGRESS"] * 2}, WEEK_MONDAY)
        add_lessons(self.user, WEEK_MONDAY, total=10, missed=2)

        outcome = accrue_week_for_user(self.user, WEEK_MONDAY)

        self.assertEqual(outcome["rating"], Decimal("24.00"))
        self.assertEqual(outcome["coins"], Decimal("24.00"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("24.00"))
        self.assertEqual(self.user.coins_balance, Decimal("24.00"))

    def test_full_marks_give_thirty(self):
        """Потолок недели — 30: 17 за КТ и 13 за посещаемость."""
        snapshot_with({"lxp-1": ["PASSED", "PASSED"]}, WEEK_MONDAY)
        add_lessons(self.user, WEEK_MONDAY, total=4, missed=0)

        outcome = accrue_week_for_user(self.user, WEEK_MONDAY)

        self.assertEqual(outcome["rating"], Decimal("30.00"))

    def test_fractional_result_keeps_two_decimals(self):
        """Пункт 2.4: два знака после запятой, а не округление до целого."""
        # Одна сданная из трёх — 33,33%: 17 × 0,3333 = 5,67.
        snapshot_with({"lxp-1": ["PASSED", "IN_PROGRESS", "IN_PROGRESS"]}, WEEK_MONDAY)

        outcome = accrue_week_for_user(self.user, WEEK_MONDAY)

        self.assertEqual(outcome["rating"], Decimal("5.67"))

    def test_missing_attendance_defers_only_that_part(self):
        """Пункт 3.6: нет занятий — посещаемость откладывается, КТ платятся."""
        snapshot_with({"lxp-1": ["PASSED"]}, WEEK_MONDAY)

        outcome = accrue_week_for_user(self.user, WEEK_MONDAY)

        self.assertEqual(outcome["rating"], Decimal("17.00"))
        self.assertEqual(outcome["deferred"], ["attendance"])

    def test_deferred_part_is_paid_when_data_arrives(self):
        """Отложенный компонент восстанавливается, а оплаченный не дублируется."""
        snapshot_with({"lxp-1": ["PASSED"]}, WEEK_MONDAY)
        accrue_week_for_user(self.user, WEEK_MONDAY)

        add_lessons(self.user, WEEK_MONDAY, total=2, missed=0)
        second = accrue_week_for_user(self.user, WEEK_MONDAY)

        self.assertEqual(second["rating"], Decimal("13.00"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("30.00"))

    def test_week_is_not_paid_twice(self):
        """Пункт 2.4: один расчётный период не оплачивается повторно."""
        snapshot_with({"lxp-1": ["PASSED"]}, WEEK_MONDAY)
        add_lessons(self.user, WEEK_MONDAY, total=2, missed=0)

        accrue_week_for_user(self.user, WEEK_MONDAY)
        repeat = accrue_week_for_user(self.user, WEEK_MONDAY)

        self.assertEqual(repeat["rating"], Decimal("0"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("30.00"))

    def test_online_presence_counts_as_attended(self):
        """Пункт 3.2: отметка об участии онлайн — это присутствие."""
        LessonAttendance.objects.create(
            user=self.user,
            lxp_class_id="online-1",
            lesson_date=WEEK_MONDAY,
            status=LessonAttendanceStatus.ONLINE,
        )

        outcome = accrue_week_for_user(self.user, WEEK_MONDAY)

        self.assertEqual(outcome["attendance_percent"], Decimal("100.00"))

    def test_week_before_season_start_is_not_paid(self):
        """Пункт 2.2: за период до запуска начисления не производятся."""
        before = WEEK_MONDAY - timedelta(days=14)
        snapshot_with({"lxp-1": ["PASSED"]}, before)
        add_lessons(self.user, before, total=2, missed=0)

        result = run_weekly_accrual(before)

        self.assertEqual(result.notes, "before_season_start")
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("0.00"))

    def test_log_carries_period_and_coins(self):
        """Пункт 10.1: в истории видны период, основание и монеты."""
        snapshot_with({"lxp-1": ["PASSED"]}, WEEK_MONDAY)
        accrue_week_for_user(self.user, WEEK_MONDAY)

        log = RatingLog.objects.get(user=self.user, source_id=f"week:{period_key(WEEK_MONDAY)}:ct")
        self.assertEqual(log.period_key, period_key(WEEK_MONDAY))
        self.assertEqual(log.coins_delta, Decimal("17.00"))
        self.assertIn("Успеваемость", log.reason)

    def test_run_covers_all_students(self):
        other = make_student("second", "lxp-2")
        snapshot_with({"lxp-1": ["PASSED"], "lxp-2": ["IN_PROGRESS"]}, WEEK_MONDAY)
        add_lessons(self.user, WEEK_MONDAY, total=2, missed=0)
        add_lessons(other, WEEK_MONDAY, total=2, missed=1)

        result = run_weekly_accrual(WEEK_MONDAY)

        self.assertEqual(result.users_considered, 2)
        self.assertEqual(result.users_paid, 2)
        self.user.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("30.00"))
        # Вторая: КТ 0% и посещаемость 50% — 13 × 0,5 = 6,50.
        self.assertEqual(other.rating_current, Decimal("6.50"))

    def test_week_start_is_monday(self):
        self.assertEqual(week_start(date(2026, 10, 25)), WEEK_MONDAY)
        self.assertEqual(week_start(WEEK_MONDAY), WEEK_MONDAY)

    def test_attendance_alone_cannot_exceed_thirteen(self):
        """Пункт 3.4: посещаемость даёт не больше 13 баллов в неделю.

        Проверяется потолок именно компонента посещаемости: данных по КТ нет,
        посещаемость полная, пар много — начисление всё равно ровно 13.
        """
        for day_offset in range(5):
            add_lessons(self.user, WEEK_MONDAY + timedelta(days=day_offset), total=6, missed=0)

        outcome = accrue_week_for_user(self.user, WEEK_MONDAY)

        self.assertEqual(outcome["attendance_percent"], Decimal("100.00"))
        self.assertEqual(outcome["rating"], Decimal("13.00"))
        self.assertEqual(outcome["coins"], Decimal("13.00"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("13.00"))

    def test_second_week_is_paid_separately(self):
        """Потолок 13 — на неделю, а не на сезон: следующая неделя платится снова."""
        add_lessons(self.user, WEEK_MONDAY, total=2, missed=0)
        accrue_week_for_user(self.user, WEEK_MONDAY)

        next_monday = WEEK_MONDAY + timedelta(days=7)
        add_lessons(self.user, next_monday, total=2, missed=0)
        second = accrue_week_for_user(self.user, next_monday)

        self.assertEqual(second["rating"], Decimal("13.00"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("26.00"))


@override_settings(
    POLOZHENIE_PERIOD=SEASON,
    POLOZHENIE_ACADEMIC={"CT_WEEKLY_MAX": Decimal("17"), "ATTENDANCE_WEEKLY_MAX": Decimal("13")},
)
class CtScopeTests(TestCase):
    """Чем считать актуальные КТ — выбор колледжа, а не зашитое поведение."""

    def setUp(self):
        self.user = make_student()

    def test_default_defers_the_component(self):
        """По умолчанию компонент не платится, пока правило не выбрано.

        На живых данных правило «решённые» давало 100% пятнадцати студентам
        из семнадцати. Платить по непроверенному правилу хуже, чем не
        платить: отложенное доплачивается, а лишнее придётся отбирать.
        """
        snapshot_with({"lxp-1": ["PASSED", "PASSED", "IN_PROGRESS"]}, WEEK_MONDAY)
        add_lessons(self.user, WEEK_MONDAY, total=2, missed=0)

        outcome = accrue_week_for_user(self.user, WEEK_MONDAY)

        self.assertIn("ct", outcome["deferred"])
        self.assertEqual(outcome["rating"], Decimal("13.00"), "посещаемость платится как обычно")

    @override_settings(POLOZHENIE_CT_SCOPE="decided", POLOZHENIE_CT_MIN_ACTUAL=1)
    def test_deferred_component_is_paid_after_the_rule_is_chosen(self):
        """Отложенное начисление доплачивается за прошедшую неделю."""
        snapshot_with({"lxp-1": ["PASSED", "PASSED", "IN_PROGRESS"]}, WEEK_MONDAY)
        add_lessons(self.user, WEEK_MONDAY, total=2, missed=0)

        with override_settings(POLOZHENIE_CT_SCOPE="deferred"):
            accrue_week_for_user(self.user, WEEK_MONDAY)

        second = accrue_week_for_user(self.user, WEEK_MONDAY)

        # Две сданные из трёх решённых: 17 × 0,6667 = 11,33.
        self.assertEqual(second["rating"], Decimal("11.33"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, Decimal("24.33"))

    @override_settings(POLOZHENIE_CT_SCOPE="decided", POLOZHENIE_CT_MIN_ACTUAL=1)
    def test_decided_scope_ignores_pending(self):
        percent, actual, passed = ct_percent_from_snapshot(
            {"d1": {"topics": [{"status": "PASSED"}, {"status": "IN_REVIEW"}]}}
        )

        self.assertEqual((actual, passed), (1, 1))
        self.assertEqual(percent, Decimal("100.00"))

    @override_settings(POLOZHENIE_CT_SCOPE="decided_with_pending", POLOZHENIE_CT_MIN_ACTUAL=1)
    def test_pending_scope_counts_review_as_unpassed(self):
        percent, actual, passed = ct_percent_from_snapshot(
            {"d1": {"topics": [{"status": "PASSED"}, {"status": "IN_REVIEW"}]}}
        )

        self.assertEqual((actual, passed), (2, 1))
        self.assertEqual(percent, Decimal("50.00"))

    @override_settings(POLOZHENIE_CT_SCOPE="decided", POLOZHENIE_CT_MIN_ACTUAL=3)
    def test_too_few_topics_defer_instead_of_giving_full_marks(self):
        """Две сданные темы из двух — это не отличная успеваемость.

        Именно так Тумов и Хамурзов получали по 17 баллов: у них всего две
        темы с решением, и обе сданы.
        """
        snapshot_with({"lxp-1": ["PASSED", "PASSED"]}, WEEK_MONDAY)

        outcome = accrue_week_for_user(self.user, WEEK_MONDAY)

        self.assertIn("ct", outcome["deferred"])
        self.assertEqual(outcome["rating"], Decimal("0"))

    @override_settings(POLOZHENIE_CT_SCOPE="decided", POLOZHENIE_CT_MIN_ACTUAL=3)
    def test_threshold_reached_pays_as_usual(self):
        snapshot_with({"lxp-1": ["PASSED", "PASSED", "IN_PROGRESS"]}, WEEK_MONDAY)

        outcome = accrue_week_for_user(self.user, WEEK_MONDAY)

        self.assertEqual(outcome["deferred"], ["attendance"])
        self.assertEqual(outcome["rating"], Decimal("11.33"))
