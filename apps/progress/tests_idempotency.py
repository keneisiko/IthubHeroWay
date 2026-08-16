"""Идемпотентность начислений и границы суток."""

from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.integrations.models import LXPSnapshot, TelegramAccountLink
from apps.progress.models import RatingLog
from apps.progress.services.lxp_rating_from_snapshot import apply_rating_from_lxp_snapshot
from apps.progress.services.rewards import local_day_start, remaining_daily_coin_budget
from apps.quests.models import Quest, QuestRewardTransaction

User = get_user_model()


def snapshot_data(lxp_uid: str) -> dict:
    """Снимок с ненулевой дельтой: две закрытые темы и ни одной открытой.

    Важно, чтобы пересчёт реально менял рейтинг, иначе идемпотентность
    не с чем сравнивать — нулевая дельта отсекается отдельной веткой.
    """
    return {
        "meta": {"partial": False},
        "control_points": {
            "ok": True,
            "data": {
                lxp_uid: {
                    "disc-1": {"topics": [{"status": "PASSED"}, {"status": "DONE"}]}
                }
            },
        },
        "attendance": {"data": {lxp_uid: {"has_attendance": True}}},
    }


class RatingIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="agent",
            email="a@nalchik.ithub.ru",
            password="x",
            callsign="agent_call",
            lxp_user_id="lxp-7",
            rating_current=300,
        )
        TelegramAccountLink.objects.create(
            user=self.user, telegram_user_id=555, telegram_chat_id=555, is_active=True
        )
        self.date = date(2026, 5, 20)
        LXPSnapshot.objects.create(date=self.date, data=snapshot_data("lxp-7"))

    def test_second_run_does_not_change_rating(self):
        """Ретрай Celery или ручной прогон за ту же дату начислял всё заново."""
        apply_rating_from_lxp_snapshot(self.date)
        self.user.refresh_from_db()
        after_first = self.user.rating_current
        logs_after_first = RatingLog.objects.filter(user=self.user).count()

        result = apply_rating_from_lxp_snapshot(self.date)

        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, after_first)
        self.assertEqual(RatingLog.objects.filter(user=self.user).count(), logs_after_first)
        self.assertEqual(result.users_updated, 0)
        self.assertIn("already_applied", result.notes)

    def test_force_allows_deliberate_recalculation(self):
        apply_rating_from_lxp_snapshot(self.date)
        logs_after_first = RatingLog.objects.filter(user=self.user).count()

        apply_rating_from_lxp_snapshot(self.date, force=True)

        self.assertGreater(RatingLog.objects.filter(user=self.user).count(), logs_after_first)

    def test_different_dates_are_applied_independently(self):
        other_date = self.date + timedelta(days=1)
        LXPSnapshot.objects.create(date=other_date, data=snapshot_data("lxp-7"))

        apply_rating_from_lxp_snapshot(self.date)
        result = apply_rating_from_lxp_snapshot(other_date)

        self.assertEqual(result.users_updated, 1)


@override_settings(TIME_ZONE="Europe/Moscow", USE_TZ=True)
class DayBoundaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="spender", email="s@test.ru", password="x", callsign="spender_call"
        )
        self.quest = Quest.objects.create(code="q1", title="Q", reward_coins=5)

    def test_day_start_is_local_midnight(self):
        moment = timezone.make_aware(datetime(2026, 6, 15, 1, 30))
        start = local_day_start(moment)
        self.assertEqual(timezone.localtime(start).hour, 0)
        self.assertEqual(timezone.localtime(start).date(), date(2026, 6, 15))

    def test_coins_earned_early_morning_count_toward_today(self):
        """Полночь по UTC — это 03:00 по Москве: награды, полученные ночью,
        засчитывались во «вчерашний» лимит, а утренний бюджет был неполным."""
        early = timezone.make_aware(datetime(2026, 6, 15, 1, 0))
        tx = QuestRewardTransaction.objects.create(
            user=self.user, quest=self.quest, coins_delta=20, rating_delta=0
        )
        QuestRewardTransaction.objects.filter(pk=tx.pk).update(granted_at=early)

        with self.settings(RATING_LIMITS={"MAX_DAILY_COINS": 20}):
            # Считаем бюджет в те же сутки, но позже — в 10 утра.
            later = timezone.make_aware(datetime(2026, 6, 15, 10, 0))
            with_patched_now = local_day_start(later)
            self.assertLessEqual(with_patched_now, early)

            remaining = remaining_daily_coin_budget(self.user)
            self.assertGreaterEqual(remaining, 0)
