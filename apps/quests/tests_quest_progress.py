"""Тесты частичного прогресса и повторного закрытия квестов.

`update_quest_progress` до сих пор был без тестов, хотя именно через него
верификаторы обновляют квесты «в процессе»: ошибка тут либо обнуляет
накопленный прогресс, либо перезаписывает уже выданную награду.

Фабрики берутся из корневого conftest — тесты проекта на unittest, поэтому
это обычные функции, а не фикстуры pytest.
"""

from django.test import TestCase

from apps.quests.models import QuestRewardTransaction, UserQuestProgress
from apps.quests.services.quest_completion import (
    complete_quest_idempotent,
    update_quest_progress,
)
from conftest import make_agent, make_quest, make_squad


class UpdateQuestProgressTests(TestCase):
    def setUp(self):
        self.user = make_agent()
        self.quest = make_quest(reward_coins=5, reward_rating_delta=3)

    def test_progress_is_created_and_updated(self):
        progress = update_quest_progress(self.user, self.quest, progress_value=0.4)

        self.assertAlmostEqual(progress.progress_value, 0.4)
        self.assertFalse(progress.is_completed)

        update_quest_progress(self.user, self.quest, progress_value=0.7)
        progress.refresh_from_db()
        self.assertAlmostEqual(progress.progress_value, 0.7)
        self.assertEqual(UserQuestProgress.objects.filter(user=self.user).count(), 1)

    def test_progress_is_clamped_to_zero_one(self):
        """Верификаторы считают долю сами и иногда отдают 1.5 или -0.2."""
        self.assertAlmostEqual(
            update_quest_progress(self.user, self.quest, progress_value=5).progress_value, 1.0
        )
        self.assertAlmostEqual(
            update_quest_progress(self.user, self.quest, progress_value=-3).progress_value, 0.0
        )

    def test_completed_quest_is_not_rolled_back(self):
        """Иначе ночной пересчёт сбрасывал бы уже закрытый квест обратно в 0."""
        complete_quest_idempotent(self.user, self.quest, reason="готово")

        progress = update_quest_progress(self.user, self.quest, progress_value=0.1)

        self.assertTrue(progress.is_completed)
        self.assertAlmostEqual(progress.progress_value, 1.0)

    def test_evidence_is_stored_only_when_passed(self):
        update_quest_progress(self.user, self.quest, progress_value=0.5, evidence={"days": 2})
        update_quest_progress(self.user, self.quest, progress_value=0.6)

        progress = UserQuestProgress.objects.get(user=self.user, quest=self.quest)
        self.assertEqual(progress.proof_payload, {"days": 2})


class CompleteQuestIdempotentTests(TestCase):
    def setUp(self):
        # Агент в отряде: в проде пользователь без отряда — исключение,
        # и тест не должен случайно опираться на squad=None.
        self.user = make_agent(squad=make_squad())
        self.quest = make_quest(reward_coins=4, reward_rating_delta=2)

    def test_reward_is_granted_once(self):
        """Верификаторы гоняются по расписанию, повторный вызов неизбежен."""
        _, first = complete_quest_idempotent(self.user, self.quest, reason="первый раз")
        _, second = complete_quest_idempotent(self.user, self.quest, reason="второй раз")

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(QuestRewardTransaction.objects.filter(user=self.user).count(), 1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.coins_balance, 4)

    def test_partial_progress_is_promoted_to_completed(self):
        update_quest_progress(self.user, self.quest, progress_value=0.3)

        progress, created = complete_quest_idempotent(self.user, self.quest, reason="добито")

        self.assertTrue(created)
        self.assertTrue(progress.is_completed)
        self.assertIsNotNone(progress.completed_at)

    def test_evidence_is_saved_with_completion(self):
        progress, _ = complete_quest_idempotent(
            self.user, self.quest, reason="hik", evidence={"source": "hik", "events": 3}
        )

        progress.refresh_from_db()
        self.assertEqual(progress.proof_payload["source"], "hik")

    def test_long_reason_does_not_break_rating_record(self):
        """Причина уходит в поле рейтинга ограниченной длины, её режут в сервисе."""
        complete_quest_idempotent(self.user, self.quest, reason="ж" * 400)

        self.user.refresh_from_db()
        self.assertEqual(self.user.rating_current, 302)
