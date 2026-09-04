"""Цель недели.

Блок «Еженедельный выбор» хранил выбор в состоянии React: на сервер он
не уходил, сбрасывался при перезагрузке страницы и ни на что не влиял —
студент нажимал «Выбрать» и получал награду за оба задания одинаково.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.quests.models import Quest, QuestRewardTransaction, QuestType, WeeklyFocus
from apps.quests.services.quest_completion import complete_quest_idempotent
from apps.quests.services.quest_periods import period_key_for
from apps.quests.services.weekly_focus import (
    FocusNotAllowed,
    current_period_key,
    focus_bonus,
    get_focus,
    is_focused,
    set_focus,
)

User = get_user_model()

FOCUS_REWARDS = {
    "WEEKLY_FOCUS_BONUS_COINS": 5,
    "WEEKLY_FOCUS_BONUS_RATING": 3,
    "DAILY_QUEST_REWARD": 3,
    "WEEKLY_QUEST_REWARD": 10,
}


def make_weekly(code: str, title: str, day=None) -> Quest:
    day = day or timezone.localdate()
    return Quest.objects.create(
        code=code,
        title=title,
        quest_type=QuestType.WEEKLY,
        period_key=period_key_for(QuestType.WEEKLY, day),
        reward_coins=15,
        reward_rating_delta=8,
    )


@override_settings(QUESTS_REWARDS=FOCUS_REWARDS)
class WeeklyFocusServiceTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="focused",
            email="focused@test.ru",
            password="x",
            callsign="focused_call",
            role=Role.AGENT,
            rating_current=300,
            coins_balance=0,
        )
        self.first = make_weekly("weekly-a", "Закрыть КТ")
        self.second = make_weekly("weekly-b", "Спринт YouGile")

    def test_focus_is_stored_for_the_week(self):
        focus = set_focus(self.user, self.first.code)

        self.assertEqual(focus.period_key, current_period_key())
        self.assertEqual(get_focus(self.user).quest, self.first)

    def test_choosing_again_replaces_previous_focus(self):
        """Цель одна: иначе «выбор» перестаёт быть выбором."""
        set_focus(self.user, self.first.code)
        set_focus(self.user, self.second.code)

        self.assertEqual(WeeklyFocus.objects.filter(user=self.user).count(), 1)
        self.assertEqual(get_focus(self.user).quest, self.second)

    def test_daily_quest_cannot_be_a_weekly_focus(self):
        daily = Quest.objects.create(code="daily-x", title="Чек-ин", quest_type=QuestType.DAILY)

        with self.assertRaises(FocusNotAllowed):
            set_focus(self.user, daily.code)

    def test_quest_from_another_week_is_rejected(self):
        old = make_weekly("weekly-old", "Прошлая неделя", timezone.localdate() - timedelta(days=14))

        with self.assertRaises(FocusNotAllowed):
            set_focus(self.user, old.code)

    def test_focus_of_another_user_does_not_leak(self):
        stranger = User.objects.create_user(
            username="stranger", email="s@test.ru", password="x", callsign="s_call"
        )
        set_focus(stranger, self.first.code)

        self.assertIsNone(get_focus(self.user))
        self.assertFalse(is_focused(self.user, self.first))

    def test_bonus_applies_only_to_the_focused_quest(self):
        set_focus(self.user, self.first.code)

        self.assertEqual(focus_bonus(self.user, self.first), (5, 3))
        self.assertEqual(focus_bonus(self.user, self.second), (0, 0))


@override_settings(QUESTS_REWARDS=FOCUS_REWARDS, RATING_LIMITS={"MAX_DAILY_COINS": 100})
class WeeklyFocusRewardTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="rewarded",
            email="rewarded@test.ru",
            password="x",
            callsign="rewarded_call",
            role=Role.AGENT,
            rating_current=300,
            coins_balance=0,
        )
        self.quest = make_weekly("weekly-reward", "Закрыть КТ")

    def test_focused_quest_pays_extra(self):
        set_focus(self.user, self.quest.code)

        complete_quest_idempotent(self.user, self.quest, reason="Автопроверка")

        self.user.refresh_from_db()
        self.assertEqual(self.user.coins_balance, 20, "15 за квест + 5 за цель недели")
        self.assertEqual(self.user.rating_current, 311, "8 за квест + 3 за цель недели")

    def test_quest_without_focus_pays_base_reward(self):
        complete_quest_idempotent(self.user, self.quest, reason="Автопроверка")

        self.user.refresh_from_db()
        self.assertEqual(self.user.coins_balance, 15)
        self.assertEqual(self.user.rating_current, 308)

    def test_other_weekly_quests_stay_rewarded(self):
        """Цель недели ничего не отключает — это акцент, а не «или/или»."""
        other = make_weekly("weekly-other", "Спринт")
        set_focus(self.user, self.quest.code)

        complete_quest_idempotent(self.user, other, reason="Автопроверка")

        self.user.refresh_from_db()
        self.assertEqual(self.user.coins_balance, 15)
        self.assertTrue(QuestRewardTransaction.objects.filter(user=self.user, quest=other).exists())


@override_settings(QUESTS_REWARDS=FOCUS_REWARDS)
class WeeklyFocusApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="api_focus",
            email="api_focus@test.ru",
            password="x",
            callsign="api_focus_call",
            role=Role.AGENT,
        )
        self.client.force_authenticate(self.user)
        self.quest = make_weekly("weekly-api", "Закрыть КТ")
        self.url = reverse("quests-weekly-focus")

    def test_get_returns_empty_focus_with_bonus_size(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["quest_code"], "")
        self.assertEqual(body["bonus_coins"], 5)
        self.assertEqual(body["bonus_rating"], 3)

    def test_post_sets_focus_and_get_returns_it(self):
        response = self.client.post(self.url, {"quest_code": self.quest.code}, format="json")
        self.assertEqual(response.status_code, 200)

        body = self.client.get(self.url).json()
        self.assertEqual(body["quest_code"], self.quest.code)
        self.assertEqual(body["quest_title"], "Закрыть КТ")

    def test_unknown_quest_is_rejected(self):
        response = self.client.post(self.url, {"quest_code": "nope"}, format="json")

        self.assertEqual(response.status_code, 400)

    def test_empty_code_is_rejected(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, 400)
