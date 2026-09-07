"""Честность недельных квестов по данным LXP.

Оба дефекта нашлись на закрытом прогоне группы 3ИТР2.9.24: посещаемость
показывала 100% в первую неделю сентября, когда занятий ещё не было,
а квест на сдачу КТ закрывался у всех — «191/1» за прошлые курсы.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.progress.models import LXPTopicState
from apps.quests.services.verifiers import (
    _attendance_percent,
    _count_ct_closed_since,
    verify_lxp_ct_closed,
)

User = get_user_model()
TODAY = date(2026, 9, 7)


class AttendanceWithoutLessonsTests(TestCase):
    def test_disciplines_without_lessons_are_not_full_attendance(self):
        """LXP отдаёт percent=100 при total=0, пока занятий не было."""
        row = {"by_discipline": {"d1": {"total": 0, "visited": 0, "percent": 100}}}

        self.assertIsNone(_attendance_percent(row))

    def test_real_lessons_outweigh_empty_disciplines(self):
        row = {
            "by_discipline": {
                "d1": {"total": 0, "visited": 0, "percent": 100},
                "d2": {"total": 4, "visited": 2, "percent": 50},
            }
        }

        self.assertEqual(_attendance_percent(row), 50.0)

    def test_percent_is_used_when_lesson_counts_are_missing(self):
        row = {"by_discipline": {"d1": {"percent": 90}, "d2": {"percent": 70}}}

        self.assertEqual(_attendance_percent(row), 80.0)


class ControlPointsWithinPeriodTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="agent", email="a@test.ru", password="x", callsign="Агент", lxp_user_id="u1"
        )

    def set_topics(self, topics: dict):
        LXPTopicState.objects.update_or_create(user=self.user, defaults={"topics": topics})

    def test_topics_from_past_courses_do_not_count(self):
        self.set_topics(
            {f"d:{i}": {"closed": True, "since": "2026-09-07", "baseline": True} for i in range(191)}
        )

        self.assertEqual(_count_ct_closed_since(self.user, TODAY - timedelta(days=6)), 0)

    def test_topic_closed_this_week_counts(self):
        self.set_topics({"d:1": {"closed": True, "since": "2026-09-05"}})

        self.assertEqual(_count_ct_closed_since(self.user, TODAY - timedelta(days=6)), 1)

    def test_topic_closed_before_the_period_does_not_count(self):
        self.set_topics({"d:1": {"closed": True, "since": "2026-08-20"}})

        self.assertEqual(_count_ct_closed_since(self.user, TODAY - timedelta(days=6)), 0)

    def test_open_topic_does_not_count(self):
        self.set_topics({"d:1": {"closed": False, "since": "2026-09-05"}})

        self.assertEqual(_count_ct_closed_since(self.user, TODAY - timedelta(days=6)), 0)

    def test_quest_is_not_completed_without_a_fresh_control_point(self):
        self.set_topics({"d:1": {"closed": True, "since": "2026-09-07", "baseline": True}})

        result = verify_lxp_ct_closed(self.user, {"min_closed": 1, "days": 7}, TODAY)

        self.assertFalse(result.completed)
        self.assertEqual(result.evidence["closed_count"], 0)

    def test_student_without_topic_state_gets_nothing(self):
        result = verify_lxp_ct_closed(self.user, {"min_closed": 1, "days": 7}, TODAY)

        self.assertFalse(result.completed)
