from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.models import Squad
from apps.integrations.models import LXPSnapshot, TelegramAccountLink
from apps.progress.models import CourseTopicNorm, LXPTopicState, RatingLog
from apps.progress.services.lxp_rating_from_snapshot import apply_rating_from_lxp_snapshot

User = get_user_model()

YEAR_SETTINGS = {
    "ACADEMIC_YEAR_START_MONTH": 9,
    "ACADEMIC_YEAR_START_DAY": 1,
    "CT_YEAR_BUDGET": 400,
    "CT_POINTS_MIN": 4,
    "CT_POINTS_MAX": 40,
    "CT_EXPECTED_TOPICS_FALLBACK": 40,
    "TOPIC_STALE_DAYS": 30,
    "STALE_PENALTY_PER_TOPIC": -20,
    "STALE_BLOCK_THRESHOLD": 2,
    "ALL_CLOSED_BONUS_COOLDOWN_DAYS": 30,
}


def snapshot_payload(topics_by_user: dict[str, list[str]]) -> dict:
    """Снимок с одной дисциплиной на студента: список статусов тем."""
    return {
        "meta": {"partial": False},
        "control_points": {
            "ok": True,
            "data": {
                uid: {
                    "disc-a": {
                        "topics": [
                            {"status": status, "topic": {"id": f"t{i}"}}
                            for i, status in enumerate(statuses)
                        ]
                    }
                }
                for uid, statuses in topics_by_user.items()
            },
        },
        "attendance": {"ok": True, "data": {uid: {"has_attendance": True} for uid in topics_by_user}},
    }


@override_settings(
    RATING_YEAR=YEAR_SETTINGS,
    RATING_KP={"CT_ALL_CLOSED_BONUS": 30},
    RATING_LIMITS={"MAX_RATING_WHEN_BLOCKED": 399},
)
class LxpRatingEventModelTests(TestCase):
    """Рейтинг начисляется за изменение, а не за текущее состояние."""

    def setUp(self):
        self.squad = Squad.objects.create(code="s1", name="Отряд 1", course=1)
        self.u = User.objects.create_user(
            username="stu1",
            email="stu1@test.ru",
            password="x",
            callsign="call_stu1",
            rating_current=300,
            unclosed_ct_count=0,
            lxp_user_id="uid-1",
            squad=self.squad,
        )
        TelegramAccountLink.objects.create(
            user=self.u, telegram_user_id=999001, telegram_chat_id=999001, is_active=True
        )
        # Норма курса: 20 тем в году → 400 / 20 = 20 за тему.
        CourseTopicNorm.objects.create(course=1, expected_topics=20)

    def _apply(self, day: date, statuses: list[str]):
        LXPSnapshot.objects.update_or_create(
            date=day, defaults={"data": snapshot_payload({"uid-1": statuses})}
        )
        return apply_rating_from_lxp_snapshot(day)

    def test_first_snapshot_only_records_baseline(self):
        """За темы, закрытые до подключения системы, рейтинг не выдаётся."""
        self._apply(date(2026, 10, 1), ["PASSED", "PASSED", "OPEN"])

        self.u.refresh_from_db()
        self.assertEqual(self.u.rating_current, 300)
        state = LXPTopicState.objects.get(user=self.u)
        self.assertTrue(state.baseline_done)
        self.assertEqual(len(state.topics), 3)

    def test_closing_topic_grants_points_once(self):
        self._apply(date(2026, 10, 1), ["OPEN", "OPEN"])
        self._apply(date(2026, 10, 2), ["PASSED", "OPEN"])

        self.u.refresh_from_db()
        self.assertEqual(self.u.rating_current, 320)

        # Та же закрытая тема в следующем снимке ничего не добавляет.
        self._apply(date(2026, 10, 3), ["PASSED", "OPEN"])
        self.u.refresh_from_db()
        self.assertEqual(self.u.rating_current, 320)

    def test_open_topic_within_deadline_costs_nothing(self):
        """Главное отличие от старой модели: открытая тема не штрафуется."""
        for offset in range(1, 8):
            self._apply(date(2026, 10, 1) + timedelta(days=offset - 1), ["OPEN", "OPEN", "OPEN"])

        self.u.refresh_from_db()
        self.assertEqual(self.u.rating_current, 300)
        self.assertEqual(self.u.unclosed_ct_count, 0)

    def test_stale_topic_is_penalized_once(self):
        self._apply(date(2026, 10, 1), ["OPEN"])
        self._apply(date(2026, 11, 5), ["OPEN"])  # 35 дней открыта

        self.u.refresh_from_db()
        self.assertEqual(self.u.rating_current, 280)
        self.assertEqual(self.u.unclosed_ct_count, 1)

        self._apply(date(2026, 11, 6), ["OPEN"])
        self.u.refresh_from_db()
        self.assertEqual(self.u.rating_current, 280, "штраф за ту же тему не повторяется")

    def test_reopened_topic_restarts_deadline(self):
        self._apply(date(2026, 10, 1), ["OPEN"])
        self._apply(date(2026, 10, 2), ["PASSED"])
        self._apply(date(2026, 11, 10), ["OPEN"])

        self.u.refresh_from_db()
        # 20 за закрытие + 30 бонуса; после переоткрытия штрафа нет — срок пошёл заново.
        self.assertEqual(self.u.rating_current, 350)

    def test_all_closed_bonus_is_granted_once_per_year(self):
        self._apply(date(2026, 10, 1), ["OPEN"])
        self._apply(date(2026, 10, 2), ["PASSED"])

        self.u.refresh_from_db()
        first = self.u.rating_current
        self.assertEqual(first, 350, "20 за тему + 30 за все закрытые КТ")

        self._apply(date(2026, 10, 3), ["PASSED"])
        self.u.refresh_from_db()
        self.assertEqual(self.u.rating_current, first, "бонус не капает ежедневно")

    def test_block_stops_growth_but_keeps_accumulated_rating(self):
        self.u.rating_current = 600
        self.u.save(update_fields=["rating_current"])

        self._apply(date(2026, 10, 1), ["OPEN", "OPEN", "OPEN"])
        self._apply(date(2026, 11, 5), ["PASSED", "OPEN", "OPEN"])

        self.u.refresh_from_db()
        # Две просроченные темы: −40 штрафа, рост заблокирован, но накопленное
        # за год не срезается до 399.
        self.assertEqual(self.u.unclosed_ct_count, 2)
        self.assertEqual(self.u.rating_current, 560)

    def test_rating_log_written_for_each_change(self):
        self._apply(date(2026, 10, 1), ["OPEN"])
        self._apply(date(2026, 10, 2), ["PASSED"])

        logs = RatingLog.objects.filter(user=self.u, delta__gt=0)
        self.assertEqual(logs.count(), 1)
        self.assertIn("closed=1", logs.first().reason)


@override_settings(
    RATING_YEAR=YEAR_SETTINGS,
    RATING_KP={"CT_ALL_CLOSED_BONUS": 30},
    RATING_LIMITS={"MAX_RATING_WHEN_BLOCKED": 399},
)
class CourseFairnessTests(TestCase):
    """Курсы с разным объёмом программы получают сопоставимый годовой максимум."""

    def _student(self, uid: str, course: int) -> User:
        squad = Squad.objects.create(code=f"s{course}", name=f"Отряд {course}", course=course)
        user = User.objects.create_user(
            username=f"stu{course}",
            email=f"stu{course}@test.ru",
            password="x",
            callsign=f"call{course}",
            rating_current=300,
            lxp_user_id=uid,
            squad=squad,
        )
        TelegramAccountLink.objects.create(
            user=user, telegram_user_id=900 + course, telegram_chat_id=900 + course, is_active=True
        )
        return user

    def test_year_totals_match_despite_different_topic_counts(self):
        # Первый курс: 40 тем за год. Третий: 10 тем за год.
        first = self._student("uid-c1", 1)
        third = self._student("uid-c3", 3)

        day0 = date(2026, 9, 1)
        LXPSnapshot.objects.create(
            date=day0,
            data=snapshot_payload({"uid-c1": ["OPEN"] * 40, "uid-c3": ["OPEN"] * 10}),
        )
        apply_rating_from_lxp_snapshot(day0)

        day1 = day0 + timedelta(days=1)
        LXPSnapshot.objects.create(
            date=day1,
            data=snapshot_payload({"uid-c1": ["PASSED"] * 40, "uid-c3": ["PASSED"] * 10}),
        )
        apply_rating_from_lxp_snapshot(day1)

        first.refresh_from_db()
        third.refresh_from_db()
        # Оба закрыли всю программу года: 400 за КТ + 30 бонуса поверх старта 300,
        # с точностью до округления цены темы.
        self.assertEqual(first.rating_current, 730)
        self.assertEqual(third.rating_current, 730)

    def test_bigger_course_earns_less_per_topic(self):
        self._student("uid-c1", 1)
        self._student("uid-c3", 3)

        day0 = date(2026, 9, 1)
        LXPSnapshot.objects.create(
            date=day0,
            data=snapshot_payload({"uid-c1": ["OPEN"] * 40, "uid-c3": ["OPEN"] * 10}),
        )
        apply_rating_from_lxp_snapshot(day0)

        day1 = day0 + timedelta(days=1)
        LXPSnapshot.objects.create(
            date=day1,
            data=snapshot_payload(
                {
                    "uid-c1": ["PASSED"] + ["OPEN"] * 39,
                    "uid-c3": ["PASSED"] + ["OPEN"] * 9,
                }
            ),
        )
        apply_rating_from_lxp_snapshot(day1)

        first = User.objects.get(username="stu1")
        third = User.objects.get(username="stu3")
        self.assertEqual(first.rating_current, 310, "40 тем в году → 10 за тему")
        self.assertEqual(third.rating_current, 340, "10 тем в году → 40 за тему")
