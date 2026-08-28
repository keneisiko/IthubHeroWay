"""Периодические квесты и дедлайн по расписанию отряда.

До этого «ежедневный» квест был одной строкой `Quest`, а награда уникальна
по паре «пользователь + квест» — значит, оплачивался он ровно один раз за всё
время. Дедлайн чек-ина при этом был жёстко 10:00, из-за чего отряд второй
смены не мог выполнить квест, приходя вовремя по своему расписанию.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role, Squad
from apps.integrations.models import ExternalEvent, TelegramAccountLink
from apps.quests.models import Quest, QuestRewardTransaction, QuestTemplate, QuestType, QuestVerifierKind
from apps.quests.services.quest_periods import ensure_period_quests, period_key_for
from apps.quests.services.quest_verification import verify_all_auto_quests
from apps.schedule.models import Schedule

User = get_user_model()


def make_squad(code: str, course: int, first_pair: time) -> Squad:
    squad = Squad.objects.create(code=code, name=f"Отряд {code}", course=course)
    for dow in range(7):
        Schedule.objects.create(
            squad=squad,
            day_of_week=dow,
            start_time=first_pair,
            end_time=time(min(first_pair.hour + 6, 23), first_pair.minute),
            is_active=True,
        )
    return squad


def make_agent(username: str, squad: Squad | None, tg_id: int) -> User:
    user = User.objects.create_user(
        username=username,
        email=f"{username}@test.ru",
        password="x",
        callsign=f"call_{username}",
        role=Role.AGENT,
        squad=squad,
        rating_current=300,
    )
    TelegramAccountLink.objects.create(
        user=user, telegram_user_id=tg_id, telegram_chat_id=tg_id, is_active=True
    )
    return user


def checkin(user: User, day: date, at: time, event_type: str = "access", late_minutes: int = 0) -> None:
    moment = timezone.make_aware(datetime.combine(day, at))
    ExternalEvent.objects.update_or_create(
        source="hik",
        external_event_id=f"{user.pk}-{day}",
        defaults={
            "user": user,
            "event_date": day,
            "event_type": event_type,
            "payload": {
                "event_type": event_type,
                "late_minutes": late_minutes,
                "event_time": moment.isoformat(),
            },
        },
    )


class PeriodInstanceTests(TestCase):
    def setUp(self):
        QuestTemplate.objects.create(
            code="daily-hik-on-time",
            title="Утренний чек-ин",
            quest_type=QuestType.DAILY,
            verifier=QuestVerifierKind.HIK_ON_TIME,
            verifier_params={"deadline_hour": 10},
            reward_coins=5,
            reward_rating_delta=2,
        )

    def test_instance_created_per_day(self):
        ensure_period_quests(date(2026, 10, 1))
        ensure_period_quests(date(2026, 10, 2))

        codes = set(Quest.objects.values_list("code", flat=True))
        self.assertEqual(
            codes, {"daily-hik-on-time:2026-10-01", "daily-hik-on-time:2026-10-02"}
        )

    def test_ensure_is_idempotent(self):
        ensure_period_quests(date(2026, 10, 1))
        result = ensure_period_quests(date(2026, 10, 1))

        self.assertEqual(result["created"], 0)
        self.assertEqual(Quest.objects.count(), 1)

    def test_weekly_key_is_shared_within_week(self):
        monday = date(2026, 10, 5)
        self.assertEqual(
            period_key_for(QuestType.WEEKLY, monday),
            period_key_for(QuestType.WEEKLY, monday + timedelta(days=4)),
        )


class DailyRewardRepeatsTests(TestCase):
    def setUp(self):
        QuestTemplate.objects.create(
            code="daily-hik-on-time",
            title="Утренний чек-ин",
            quest_type=QuestType.DAILY,
            verifier=QuestVerifierKind.HIK_ON_TIME,
            verifier_params={"deadline_hour": 10},
            reward_coins=5,
            reward_rating_delta=2,
        )
        self.squad = make_squad("morning", 1, time(8, 30))
        self.user = make_agent("daily_hero", self.squad, 700001)

    def test_reward_is_granted_every_day(self):
        days = [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)]
        for day in days:
            checkin(self.user, day, time(8, 25))
            verify_all_auto_quests(target_date=day, quest_types=[QuestType.DAILY])

        self.user.refresh_from_db()
        self.assertEqual(QuestRewardTransaction.objects.filter(user=self.user).count(), 3)
        self.assertEqual(self.user.coins_balance, 15)
        self.assertEqual(self.user.rating_current, 306)

    def test_same_day_rerun_pays_once(self):
        day = date(2026, 10, 1)
        checkin(self.user, day, time(8, 25))
        verify_all_auto_quests(target_date=day, quest_types=[QuestType.DAILY])
        verify_all_auto_quests(target_date=day, quest_types=[QuestType.DAILY])

        self.user.refresh_from_db()
        self.assertEqual(QuestRewardTransaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.user.coins_balance, 5)


class ScheduleDeadlineTests(TestCase):
    """Вторая смена, приходящая вовремя по своему расписанию, выполняет квест."""

    def setUp(self):
        QuestTemplate.objects.create(
            code="daily-hik-on-time",
            title="Утренний чек-ин",
            quest_type=QuestType.DAILY,
            verifier=QuestVerifierKind.HIK_ON_TIME,
            verifier_params={"deadline_hour": 10},
            reward_coins=5,
            reward_rating_delta=2,
        )
        self.morning = make_agent("first_shift", make_squad("m", 1, time(8, 30)), 700002)
        self.evening = make_agent("second_shift", make_squad("e", 3, time(12, 30)), 700003)

    def test_both_shifts_complete_when_on_time(self):
        day = date(2026, 10, 1)
        checkin(self.morning, day, time(8, 25))
        checkin(self.evening, day, time(12, 25))

        verify_all_auto_quests(target_date=day, quest_types=[QuestType.DAILY])

        self.morning.refresh_from_db()
        self.evening.refresh_from_db()
        self.assertEqual(self.morning.coins_balance, 5)
        self.assertEqual(self.evening.coins_balance, 5, "приход к своей первой паре — не опоздание")

    def test_late_for_own_schedule_does_not_complete(self):
        day = date(2026, 10, 1)
        checkin(self.evening, day, time(13, 10), event_type="late", late_minutes=40)

        verify_all_auto_quests(target_date=day, quest_types=[QuestType.DAILY])

        self.evening.refresh_from_db()
        self.assertEqual(self.evening.coins_balance, 0)

    def test_squad_without_schedule_falls_back_to_template_deadline(self):
        loner = make_agent("no_squad", None, 700004)
        day = date(2026, 10, 1)
        checkin(loner, day, time(9, 30))

        verify_all_auto_quests(target_date=day, quest_types=[QuestType.DAILY])

        loner.refresh_from_db()
        self.assertEqual(loner.coins_balance, 5)
