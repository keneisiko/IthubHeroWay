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


class BaselineSurvivesNextSnapshotTests(TestCase):
    """Метка первого снимка теряется — и «191/1» возвращается.

    На сервере квест снова засчитался всем: при втором снимке записи тем
    переписывались без `baseline`, тема прошлого курса оставалась с датой
    базы, а та попадала внутрь недели.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="agent2", email="a2@test.ru", password="x", callsign="Агент2", lxp_user_id="u2"
        )

    def apply_snapshot(self, closed_map: dict, snapshot_date: date):
        from apps.progress.services.lxp_rating_from_snapshot import _apply_topic_transitions

        state, _ = LXPTopicState.objects.get_or_create(user=self.user)
        _apply_topic_transitions(
            state, closed_map, snapshot_date, per_topic_points=4, stale_days=30, stale_penalty=-20
        )
        state.save()
        return state

    def test_baseline_topics_stay_excluded_after_second_snapshot(self):
        base_date = date(2026, 9, 17)
        LXPTopicState.objects.create(
            user=self.user,
            topics={f"d:{i}": {"closed": True, "since": base_date.isoformat(), "baseline": True} for i in range(191)},
            baseline_done=True,
            last_snapshot_date=base_date,
        )

        self.apply_snapshot({f"d:{i}": True for i in range(191)}, date(2026, 9, 18))

        self.assertEqual(_count_ct_closed_since(self.user, date(2026, 9, 14)), 0)

    def test_topic_closed_after_baseline_still_counts(self):
        base_date = date(2026, 9, 17)
        LXPTopicState.objects.create(
            user=self.user,
            topics={"d:old": {"closed": True, "since": base_date.isoformat(), "baseline": True},
                    "d:new": {"closed": False, "since": base_date.isoformat(), "baseline": True}},
            baseline_done=True,
            last_snapshot_date=base_date,
        )

        self.apply_snapshot({"d:old": True, "d:new": True}, date(2026, 9, 18))

        # Свежесданная тема засчитывается, хотя и была в первом снимке.
        self.assertEqual(_count_ct_closed_since(self.user, date(2026, 9, 14)), 1)
