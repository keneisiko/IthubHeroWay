"""Выдача нашивок по справочнику метрик.

Движок понимал одно условие — число выполненных квестов, — поэтому каталог
состоял из трёх нашивок, которые по сути одна метрика с тремя порогами.
Данные для остальных лежали в базе и не использовались.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Role
from apps.badges.catalog import BADGES
from apps.badges.metrics import SUPPORTED_CONDITION_KEYS, compute, required_metrics
from apps.badges.models import Badge, UserBadge
from apps.badges.services import award_badges_for_user
from apps.integrations.models import TelegramAccountLink
from apps.progress.models import UserStrike
from apps.social.models import Respect

User = get_user_model()


def make_badge(code: str, condition: dict, coins: int = 0) -> Badge:
    return Badge.objects.create(
        code=code, title=code, condition=condition, reward_coins=coins, is_active=True
    )


class MetricAwardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="agent",
            email="a@nalchik.ithub.ru",
            password="x",
            callsign="agent_call",
            role=Role.AGENT,
        )

    def test_rating_threshold(self):
        badge = make_badge("rating-250", {"rating_at_least": 250})
        self.user.rating_current = Decimal("249.99")
        self.user.save(update_fields=["rating_current"])

        self.assertEqual(award_badges_for_user(self.user), [])

        self.user.rating_current = Decimal("250.00")
        self.user.save(update_fields=["rating_current"])

        awarded = award_badges_for_user(self.user)
        self.assertEqual([ub.badge_id for ub in awarded], [badge.pk])

    def test_late_streak_threshold(self):
        make_badge("streak-7", {"late_streak_at_least": 7})
        UserStrike.objects.create(user=self.user, late_strike=7)

        self.assertEqual(len(award_badges_for_user(self.user)), 1)

    def test_flag_condition_requires_true(self):
        make_badge("tg", {"telegram_linked": True})

        self.assertEqual(award_badges_for_user(self.user), [])

        TelegramAccountLink.objects.create(
            user=self.user, telegram_user_id=77, telegram_chat_id=77, is_active=True
        )
        self.user.refresh_from_db()

        self.assertEqual(len(award_badges_for_user(self.user)), 1)

    def test_several_conditions_must_all_hold(self):
        make_badge("combo", {"rating_at_least": 100, "respects_given_at_least": 2})
        self.user.rating_current = Decimal("150")
        self.user.save(update_fields=["rating_current"])
        peer = User.objects.create_user(
            username="peer", password="x", callsign="peer_call", role=Role.AGENT
        )
        Respect.objects.create(from_user=self.user, to_user=peer)

        self.assertEqual(award_badges_for_user(self.user), [], "одного условия мало")

        Respect.objects.create(from_user=self.user, to_user=peer)

        self.assertEqual(len(award_badges_for_user(self.user)), 1)

    def test_badge_is_not_awarded_twice(self):
        make_badge("once", {"rating_at_least": 0}, coins=5)

        first = award_badges_for_user(self.user)
        second = award_badges_for_user(self.user)

        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(UserBadge.objects.filter(user=self.user).count(), 1)

    def test_unknown_condition_warns_and_does_not_award(self):
        make_badge("typo", {"ratng_at_least": 1})

        with self.assertLogs("apps.badges.services", level="WARNING"):
            self.assertEqual(award_badges_for_user(self.user), [])

    def test_only_needed_metrics_are_computed(self):
        """Лишние метрики не считаются: иначе прогон делал бы десяток
        запросов на каждого студента ради условий, которых в каталоге нет."""
        needed = required_metrics([{"rating_at_least": 10}, {"manual": True}])

        self.assertEqual(needed, {"rating_at_least"})
        self.assertEqual(set(compute(self.user, needed)), {"rating_at_least"})


class CatalogTests(TestCase):
    """Каталог должен быть выдаваемым: опечатка в условии — это молчащая нашивка."""

    def test_every_condition_key_is_supported(self):
        for row in BADGES:
            with self.subTest(code=row["code"]):
                unknown = set(row["condition"]) - SUPPORTED_CONDITION_KEYS
                self.assertEqual(unknown, set())

    def test_codes_are_unique(self):
        codes = [row["code"] for row in BADGES]

        self.assertEqual(len(codes), len(set(codes)))

    def test_titles_and_descriptions_are_russian(self):
        """Студент видит названия, поэтому латиницы в них быть не должно."""
        latin = set("abcdefghijklmnopqrstuvwxyz")
        for row in BADGES:
            with self.subTest(code=row["code"]):
                self.assertTrue(row["title"].strip())
                self.assertTrue(row["description"].strip())
                self.assertFalse(latin & set(row["title"].lower()), row["title"])

    def test_automatic_badges_outnumber_manual(self):
        manual = [row for row in BADGES if row["condition"].get("manual")]

        self.assertGreater(len(BADGES) - len(manual), len(manual))

    def test_badges_never_grant_rating(self):
        """Источники рейтинга перечислены в Положении исчерпывающе."""
        for row in BADGES:
            with self.subTest(code=row["code"]):
                self.assertNotIn("reward_rating_delta", row)
