"""Карта пути в профиле.

Поле `path_reached` бэкенд не отдавал вовсе, и фронт подставлял `['entry']`:
у любого студента была пройдена ровно одна веха, сколько бы он ни сделал.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Role
from apps.badges.models import Badge, UserBadge
from apps.integrations.models import TelegramAccountLink
from apps.progress.models import RatingChangeSource, RatingLog
from apps.progress.services.path_map import (
    GRADUATION_BADGE_CODE,
    INTERNSHIP_BADGE_CODE,
    PATH_ORDER,
    path_reached,
)
from apps.quests.models import (
    Quest,
    QuestRewardTransaction,
    QuestType,
    SelfReportProof,
    SelfReportProofStatus,
    UserQuestProgress,
)

User = get_user_model()


class PathMapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="walker",
            email="walker@test.ru",
            password="x",
            callsign="walker_call",
            role=Role.AGENT,
        )
        TelegramAccountLink.objects.create(
            user=self.user, telegram_user_id=700100, telegram_chat_id=700100, is_active=True
        )
        self.daily = Quest.objects.create(code="d1", title="Ежедневный", quest_type=QuestType.DAILY)
        self.weekly = Quest.objects.create(code="w1", title="Недельный", quest_type=QuestType.WEEKLY)

    def test_account_without_telegram_has_no_milestones(self):
        """Без привязки студент даже войти не может — путь не начат."""
        TelegramAccountLink.objects.filter(user=self.user).update(is_active=False)
        # Перечитываем: связь telegram_link кешируется на объекте пользователя.
        user = User.objects.get(pk=self.user.pk)

        self.assertEqual(path_reached(user), [])

    def test_activated_account_reaches_entry(self):
        self.assertEqual(path_reached(self.user), ["entry"])

    def test_first_quest_reward_opens_first_win(self):
        QuestRewardTransaction.objects.create(
            user=self.user, quest=self.daily, coins_delta=5, rating_delta=2
        )

        self.assertIn("first_win", path_reached(self.user))

    def test_negative_rating_opens_first_fail(self):
        RatingLog.objects.create(
            user=self.user,
            value_before=300,
            value_after=297,
            delta=-3,
            source=RatingChangeSource.SYSTEM,
            reason="Опоздание",
        )

        self.assertIn("first_fail", path_reached(self.user))

    def test_positive_rating_does_not_open_first_fail(self):
        RatingLog.objects.create(
            user=self.user,
            value_before=300,
            value_after=320,
            delta=20,
            source=RatingChangeSource.SYSTEM,
            reason="Закрыта КТ",
        )

        self.assertNotIn("first_fail", path_reached(self.user))

    def test_weekly_quest_opens_first_mission(self):
        UserQuestProgress.objects.create(user=self.user, quest=self.weekly, is_completed=True)

        self.assertIn("first_mission", path_reached(self.user))

    def test_daily_quest_does_not_open_first_mission(self):
        """Миссия — это недельный квест, а не отметка на турникете."""
        UserQuestProgress.objects.create(user=self.user, quest=self.daily, is_completed=True)

        self.assertNotIn("first_mission", path_reached(self.user))

    def test_approved_self_report_opens_product(self):
        progress = UserQuestProgress.objects.create(user=self.user, quest=self.daily)
        SelfReportProof.objects.create(
            quest=self.daily,
            user=self.user,
            quest_progress=progress,
            comment="Готов мини-проект",
            status=SelfReportProofStatus.APPROVED,
        )

        self.assertIn("product", path_reached(self.user))

    def test_pending_self_report_does_not_open_product(self):
        progress = UserQuestProgress.objects.create(user=self.user, quest=self.daily)
        SelfReportProof.objects.create(
            quest=self.daily,
            user=self.user,
            quest_progress=progress,
            comment="Ещё на проверке",
            status=SelfReportProofStatus.PENDING,
        )

        self.assertNotIn("product", path_reached(self.user))

    def test_last_milestones_come_from_curator_badges(self):
        for code in (INTERNSHIP_BADGE_CODE, GRADUATION_BADGE_CODE):
            badge = Badge.objects.create(code=code, title=code)
            UserBadge.objects.create(user=self.user, badge=badge)

        reached = path_reached(self.user)

        self.assertIn("internship", reached)
        self.assertIn("graduation", reached)

    def test_result_follows_map_order(self):
        """Фронт считает последнюю пройденную точку по порядку в списке."""
        QuestRewardTransaction.objects.create(
            user=self.user, quest=self.daily, coins_delta=5, rating_delta=2
        )
        UserQuestProgress.objects.create(user=self.user, quest=self.weekly, is_completed=True)
        badge = Badge.objects.create(code=GRADUATION_BADGE_CODE, title="Выпуск")
        UserBadge.objects.create(user=self.user, badge=badge)

        reached = path_reached(self.user)

        positions = [PATH_ORDER.index(code) for code in reached]
        self.assertEqual(positions, sorted(positions))
