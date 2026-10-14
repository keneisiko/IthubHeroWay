"""Разбор статусов тем LXP.

Статусы берутся из живого снимка (574 студента, 131 833 темы), а не
выдуманы: поиск по подстроке читал `NOT_PASSED_YET` как сданную тему, и это
91,6% всех записей. Одновременно `MASTERED` не попадала ни под один маркер
и считалась несданной.
"""

from __future__ import annotations

from django.test import TestCase, override_settings

from apps.progress.services.ct_status import is_topic_closed
from apps.progress.services.polozhenie_academic import is_future_topic, is_pending_topic

# Все статусы, которые встретились в снимке 2026-10-12, с их долей.
LIVE_STATUSES = (
    "NOT_PASSED_YET",
    "PASSED",
    "IN_REVIEW",
    "IN_PROGRESS",
    "MASTERED",
    "FAILED",
    "FOR_REVISION",
    "NOT_MASTERED",
    "FOR_REWORK",
    "",
)


class ClosedStatusTests(TestCase):
    def test_not_passed_yet_is_not_closed(self):
        """Главная ошибка: в NOT_PASSED_YET есть подстрока PASSED."""
        self.assertFalse(is_topic_closed("NOT_PASSED_YET"))

    def test_not_mastered_is_not_closed(self):
        self.assertFalse(is_topic_closed("NOT_MASTERED"))

    def test_passed_is_closed(self):
        self.assertTrue(is_topic_closed("PASSED"))

    def test_mastered_is_closed(self):
        """«Освоена» — это сдано, а под прежние маркеры статус не попадал."""
        self.assertTrue(is_topic_closed("MASTERED"))

    def test_russian_negation_is_respected(self):
        self.assertFalse(is_topic_closed("НЕ ЗАЧТЕНО"))
        self.assertTrue(is_topic_closed("Зачтено"))

    def test_case_and_prefix_do_not_matter(self):
        self.assertTrue(is_topic_closed("topic_passed"))
        self.assertTrue(is_topic_closed("TOPIC_PASSED"))

    def test_unknown_status_is_not_closed(self):
        """Незнакомый статус трактуем как незакрытый — безопасная сторона."""
        self.assertFalse(is_topic_closed("WAITING_FOR_SOMETHING"))

    def test_empty_status_is_not_closed(self):
        self.assertFalse(is_topic_closed(""))
        self.assertFalse(is_topic_closed(None))

    def test_in_progress_statuses_are_not_closed(self):
        for status in ("IN_PROGRESS", "IN_REVIEW", "FAILED", "FOR_REVISION", "FOR_REWORK"):
            with self.subTest(status=status):
                self.assertFalse(is_topic_closed(status))


class TopicClassificationTests(TestCase):
    """Каждый живой статус попадает ровно в одну категорию."""

    def _category(self, status: str) -> str:
        if is_future_topic(status):
            return "future"
        if is_pending_topic(status):
            return "pending"
        return "closed" if is_topic_closed(status) else "open"

    def test_live_statuses_are_classified_as_expected(self):
        expected = {
            "NOT_PASSED_YET": "future",
            "PASSED": "closed",
            "MASTERED": "closed",
            "IN_REVIEW": "pending",
            "IN_PROGRESS": "open",
            "FAILED": "open",
            "FOR_REVISION": "open",
            "NOT_MASTERED": "open",
            "FOR_REWORK": "open",
            "": "future",
        }
        for status in LIVE_STATUSES:
            with self.subTest(status=status or "(пусто)"):
                self.assertEqual(self._category(status), expected[status])

    def test_future_and_pending_are_disjoint(self):
        for status in LIVE_STATUSES:
            with self.subTest(status=status or "(пусто)"):
                self.assertFalse(is_future_topic(status) and is_pending_topic(status))

    @override_settings(POLOZHENIE_PENDING_TOPIC_MARKERS=())
    def test_pending_can_be_counted_as_unpassed(self):
        """Решение по «на проверке» — настройка, а не зашитое поведение."""
        self.assertFalse(is_pending_topic("IN_REVIEW"))
        self.assertEqual(self._category("IN_REVIEW"), "open")
