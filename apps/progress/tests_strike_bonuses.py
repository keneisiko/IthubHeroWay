"""Тесты бонусов за серии.

Модуль на 145 строк не имел ни одного теста, а содержал две ошибки,
напрямую влиявшие на рейтинг: ежедневное повторное начисление награды
за веху и работу с датой в UTC вместо часового пояса проекта.
"""

from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.integrations.models import ExternalEvent, LXPSnapshot, TelegramAccountLink
from apps.progress.models import RatingLog, UserStrike
from apps.progress.services.late_penalties import (
    attendance_streak_milestone,
    late_streak_milestone,
)
from apps.progress.services.strike_bonuses import apply_strike_bonuses, users_with_late_on_date

User = get_user_model()


class MilestoneTests(TestCase):
    def test_late_milestones_are_ranges(self):
        self.assertEqual(late_streak_milestone(6), 0)
        self.assertEqual(late_streak_milestone(7), 7)
        self.assertEqual(late_streak_milestone(13), 7)
        self.assertEqual(late_streak_milestone(14), 14)
        self.assertEqual(late_streak_milestone(20), 14)
        self.assertEqual(late_streak_milestone(21), 21)
        self.assertEqual(late_streak_milestone(40), 21)

    def test_attendance_milestone(self):
        self.assertEqual(attendance_streak_milestone(6), 0)
        self.assertEqual(attendance_streak_milestone(7), 7)
        self.assertEqual(attendance_streak_milestone(30), 7)


class StrikeBonusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="streaker",
            email="streak@nalchik.ithub.ru",
            password="x",
            callsign="streak_call",
            lxp_user_id="lxp-1",
            rating_current=300,
        )
        TelegramAccountLink.objects.create(
            user=self.user, telegram_user_id=101, telegram_chat_id=101, is_active=True
        )

    def _snapshot(self, day: date, has_attendance: bool = True):
        LXPSnapshot.objects.update_or_create(
            date=day,
            defaults={
                "data": {
                    "attendance": {"data": {"lxp-1": {"has_attendance": has_attendance}}},
                }
            },
        )

    def _set_strike(self, *, late_days: int, last_late: date):
        strike, _ = UserStrike.objects.get_or_create(user=self.user)
        strike.late_strike = late_days
        strike.last_late_date = last_late
        strike.save()
        return strike

    def test_milestone_bonus_is_granted_once_per_streak(self):
        """Награда за 7–13 дней одна и та же, поэтому раньше она капала
        каждый день: ключ включал текущее число дней и дату прогона."""
        day_one = date(2026, 6, 10)

        # Серия достигла 7 дней и продолжается: 7-й, 8-й, 9-й день подряд.
        for offset in range(3):
            run_date = day_one + timedelta(days=offset)
            self._snapshot(run_date - timedelta(days=1))
            self._set_strike(late_days=7 + offset, last_late=run_date - timedelta(days=1))
            apply_strike_bonuses(run_date)

        bonuses = RatingLog.objects.filter(
            user=self.user, source_id__startswith="late_streak:"
        )
        self.assertEqual(bonuses.count(), 1, "бонус за веху должен начисляться один раз")

    def test_new_streak_after_break_can_earn_milestone_again(self):
        """После обрыва серии веху можно заработать заново."""
        first_run = date(2026, 6, 10)
        self._snapshot(first_run - timedelta(days=1))
        self._set_strike(late_days=7, last_late=first_run - timedelta(days=1))
        apply_strike_bonuses(first_run)

        # Новая серия, начавшаяся заметно позже.
        second_run = date(2026, 7, 20)
        self._snapshot(second_run - timedelta(days=1))
        self._set_strike(late_days=7, last_late=second_run - timedelta(days=1))
        apply_strike_bonuses(second_run)

        self.assertEqual(
            RatingLog.objects.filter(user=self.user, source_id__startswith="late_streak:").count(),
            2,
        )

    def test_no_bonus_below_first_milestone(self):
        run_date = date(2026, 6, 10)
        self._snapshot(run_date - timedelta(days=1))
        self._set_strike(late_days=5, last_late=run_date - timedelta(days=1))

        apply_strike_bonuses(run_date)

        self.assertFalse(
            RatingLog.objects.filter(user=self.user, source_id__startswith="late_streak:").exists()
        )

    def test_uses_local_date_by_default(self):
        """`date.today()` на сервере в UTC давал вчерашнюю дату по Москве,
        и «вчера» уезжало на два дня назад."""
        result = apply_strike_bonuses()
        self.assertEqual(result["date"], timezone.localdate().isoformat())


class LateLookupTests(TestCase):
    def test_late_users_are_collected_in_single_query(self):
        user = User.objects.create_user(
            username="late1", email="l1@test.ru", password="x", callsign="l1"
        )
        other = User.objects.create_user(
            username="late2", email="l2@test.ru", password="x", callsign="l2"
        )
        day = date(2026, 6, 15)
        moment = timezone.make_aware(datetime(2026, 6, 15, 9, 30))

        ExternalEvent.objects.create(
            source="hik",
            external_event_id="e1",
            payload={"event_type": "late", "user_id": user.pk, "event_time": moment.isoformat()},
        )
        ExternalEvent.objects.create(
            source="hik",
            external_event_id="e2",
            payload={"event_type": "access", "user_id": other.pk, "event_time": moment.isoformat()},
        )

        with self.assertNumQueries(1):
            late_ids = users_with_late_on_date(day)

        self.assertEqual(late_ids, {user.pk})

    def test_other_days_are_not_counted(self):
        user = User.objects.create_user(
            username="late3", email="l3@test.ru", password="x", callsign="l3"
        )
        moment = timezone.make_aware(datetime(2026, 6, 14, 9, 30))
        ExternalEvent.objects.create(
            source="hik",
            external_event_id="e3",
            payload={"event_type": "late", "user_id": user.pk, "event_time": moment.isoformat()},
        )

        self.assertEqual(users_with_late_on_date(date(2026, 6, 15)), set())
