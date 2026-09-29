"""Квест «Неделя без пропусков» по отметкам занятий.

Процент посещаемости за семестр не отвечает на вопрос «был ли студент на
этой неделе»: у бросившего ходить вчера и у пропускавшего в сентябре он
одинаковый. Отметки по парам отвечают.
"""

from __future__ import annotations

from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.progress.models import LessonAttendance, LessonAttendanceStatus
from apps.quests.services.verifiers import verify_lxp_no_misses

User = get_user_model()
FRIDAY = date(2026, 9, 25)


class LxpNoMissesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="agent", email="a@test.ru", password="x", callsign="Агент"
        )

    def mark(self, day: date, status: str, class_id: str):
        LessonAttendance.objects.create(
            user=self.user,
            lxp_class_id=class_id,
            lesson_date=day,
            starts_at=time(9, 0),
            discipline="Алгоритмы",
            status=status,
        )

    def verify(self, **params):
        return verify_lxp_no_misses(self.user, {"days": 7, **params}, FRIDAY)

    def test_week_without_misses_completes_the_quest(self):
        self.mark(FRIDAY, LessonAttendanceStatus.PRESENT, "c1")
        self.mark(date(2026, 9, 24), LessonAttendanceStatus.ONLINE, "c2")

        result = self.verify()

        self.assertTrue(result.completed)
        self.assertEqual(result.evidence["missed"], 0)

    def test_single_miss_fails_the_quest(self):
        self.mark(FRIDAY, LessonAttendanceStatus.PRESENT, "c1")
        self.mark(date(2026, 9, 24), LessonAttendanceStatus.MISSED, "c2")

        result = self.verify()

        self.assertFalse(result.completed)
        self.assertEqual(result.evidence["missed"], 1)

    def test_no_marks_at_all_is_not_a_perfect_week(self):
        """Тот же изъян, что чинили у посещаемости и опозданий."""
        result = self.verify()

        self.assertFalse(result.completed)
        self.assertIn("Нет данных", result.message)

    def test_marks_outside_the_period_are_ignored(self):
        self.mark(date(2026, 9, 10), LessonAttendanceStatus.MISSED, "c-old")
        self.mark(FRIDAY, LessonAttendanceStatus.PRESENT, "c1")

        result = self.verify()

        self.assertTrue(result.completed)
        self.assertEqual(result.evidence["lessons"], 1)

    def test_allowance_can_be_relaxed(self):
        self.mark(FRIDAY, LessonAttendanceStatus.PRESENT, "c1")
        self.mark(date(2026, 9, 24), LessonAttendanceStatus.MISSED, "c2")

        result = self.verify(max_missed=1)

        self.assertTrue(result.completed)

    def test_progress_shows_the_share_attended(self):
        self.mark(FRIDAY, LessonAttendanceStatus.PRESENT, "c1")
        self.mark(date(2026, 9, 24), LessonAttendanceStatus.MISSED, "c2")

        self.assertAlmostEqual(self.verify().progress, 0.5)
