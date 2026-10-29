"""«Царь горы»: монеты за места в топе, серия, свержение, отряд-лидер."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import Role, Squad, User
from apps.badges.models import Badge, BadgeRarity, UserBadge
from apps.progress.models import RatingLog
from apps.progress.services.king_of_hill import pay_daily_top, pay_weekly_squad_leader

DAY = date(2026, 11, 10)
NOTIFY = "apps.progress.services.king_of_hill.notify_user"


def student(name: str, rating: float, squad: Squad | None = None) -> User:
    return User.objects.create_user(
        username=name, password="x", callsign=name, role=Role.AGENT, is_active=True,
        rating_current=rating, squad=squad,
    )


def coins(user: User) -> int:
    user.refresh_from_db()
    return int(user.coins_balance)


@patch(NOTIFY)
class KingOfHillDailyTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="s1", name="S1", course=2)
        self.a = student("a", 50, self.squad)
        self.b = student("b", 40)
        self.c = student("c", 30)
        self.d = student("d", 20)
        self.zero = student("zero", 0)

    def test_top_three_paid_and_rating_untouched(self, _notify):
        pay_daily_top(DAY)
        self.assertEqual([coins(u) for u in (self.a, self.b, self.c, self.d)], [4 + 1, 2, 1, 0])
        self.a.refresh_from_db()
        self.assertEqual(int(self.a.rating_current), 50, "только монеты, рейтинг не растёт")

    def test_rerun_with_changed_order_does_not_pay_same_place_twice(self, _notify):
        pay_daily_top(DAY)
        User.objects.filter(pk=self.d.pk).update(rating_current=100)
        pay_daily_top(DAY)
        self.assertEqual(RatingLog.objects.filter(source_id=f"king:top1:{DAY}").count(), 1)
        self.assertEqual(coins(self.d), 0)

    def test_dethroning_yesterdays_king_pays_bonus(self, _notify):
        pay_daily_top(DAY - timedelta(days=1))
        User.objects.filter(pk=self.b.pk).update(rating_current=60)
        before = coins(self.b)
        pay_daily_top(DAY)
        self.assertEqual(coins(self.b) - before, 4 + 5)

    def test_seven_days_on_top_gives_streak_bonus_and_badge(self, _notify):
        Badge.objects.create(code="king-of-hill", title="Царь горы", rarity=BadgeRarity.RARE, condition={"manual": True})
        for back in range(6, 0, -1):
            pay_daily_top(DAY - timedelta(days=back))
        before = coins(self.a)
        pay_daily_top(DAY)
        self.assertEqual(coins(self.a) - before, 4 + 1 + 15)
        self.assertTrue(UserBadge.objects.filter(user=self.a, badge__code="king-of-hill").exists())

    def test_student_with_zero_rating_gets_nothing(self, _notify):
        User.objects.filter(role=Role.AGENT).exclude(pk=self.zero.pk).update(rating_current=0)
        pay_daily_top(DAY)
        self.assertFalse(RatingLog.objects.filter(source="king").exists())


@patch(NOTIFY)
class SquadLeaderWeeklyTests(TestCase):
    def test_members_of_leading_squad_get_coins_once(self, _notify):
        top = Squad.objects.create(code="top", name="Top", course=1)
        low = Squad.objects.create(code="low", name="Low", course=1)
        x, y = student("x", 30, top), student("y", 10, top)
        z = student("z", 5, low)
        pay_weekly_squad_leader()
        pay_weekly_squad_leader()
        self.assertEqual([coins(x), coins(y), coins(z)], [5, 5, 0])
