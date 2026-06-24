from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.progress.services.rewards import max_daily_coins
from apps.quests.models import Quest, QuestType
from apps.quests.services.quest_completion import complete_quest_idempotent


class DailyCoinCapTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="coincap", password="x", callsign="coincap")

    def test_seven_three_coin_quests_cap_at_twenty(self):
        cap = max_daily_coins()
        self.assertEqual(cap, 20)
        for i in range(7):
            quest = Quest.objects.create(
                code=f"daily-{i}",
                title=f"Daily {i}",
                quest_type=QuestType.DAILY,
                reward_coins=3,
                reward_rating_delta=0,
                is_active=True,
            )
            complete_quest_idempotent(self.user, quest, reason="test")
        self.user.refresh_from_db()
        self.assertEqual(self.user.coins_balance, 20)
