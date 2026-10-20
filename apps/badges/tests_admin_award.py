"""Выдача нашивки вручную через админку.

Часть нашивок автомат выдать не может: «Стажировка» и «Выпуск» платформа
сама не узнаёт. Руководство персонала описывало экран «Значки пользователей
→ Добавить», но добавление было запрещено с первого коммита админки — кнопки
не существовало, и выдать такую нашивку было нельзя ничем, кроме shell.
"""

from __future__ import annotations

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase

from apps.accounts.models import Role
from apps.badges.admin import UserBadgeAdmin
from apps.badges.models import Badge, UserBadge

User = get_user_model()

# Монеты за нашивку идут через общий дневной предел (MAX_DAILY_COINS = 10) —
# тот же, что и у автоматической выдачи. Нашивка дороже предела приходит
# урезанной, и админ должен увидеть предупреждение, а не тихую недостачу.
BADGE_COINS = 50
DAILY_CAP = 10


class UserBadgeAdminAwardTests(TestCase):
    def setUp(self):
        self.admin = UserBadgeAdmin(UserBadge, AdminSite())
        self.staff = User.objects.create_user(
            username="curator", password="x", role=Role.CURATOR, is_staff=True
        )
        self.agent = User.objects.create_user(
            username="agent_badge", password="x", callsign="agent_badge", role=Role.AGENT
        )
        self.badge = Badge.objects.create(
            code="path-internship",
            title="Стажировка",
            reward_coins=BADGE_COINS,
            is_active=True,
        )
        self.request = RequestFactory().post("/admin/")
        self.request.user = self.staff
        # message_user пишет через фреймворк сообщений, а у голого запроса
        # из RequestFactory его нет.
        self.request.session = {}
        self.request._messages = FallbackStorage(self.request)

    def _award(self) -> UserBadge:
        user_badge = UserBadge(user=self.agent, badge=self.badge)
        self.admin.save_model(self.request, user_badge, form=None, change=False)
        return user_badge

    def test_adding_is_allowed(self):
        """Без этого в админке нет кнопки «Добавить»."""
        self.assertTrue(self.admin.has_add_permission(self.request))

    def test_badge_is_awarded(self):
        self._award()

        self.assertTrue(UserBadge.objects.filter(user=self.agent, badge=self.badge).exists())

    def test_coins_are_granted_like_the_rule_engine_does(self):
        """Ровно та же ветка начисления, что и у автоматической выдачи."""
        before = self.agent.coins_balance

        self._award()

        self.agent.refresh_from_db()
        self.assertEqual(self.agent.coins_balance, before + DAILY_CAP)

    def test_partial_grant_is_reported(self):
        """Молча выдать меньше монет нельзя: выдача выглядела бы полной."""
        self._award()

        messages = [str(m) for m in self.request._messages]
        self.assertTrue(messages, "предупреждение об урезанном начислении не показано")
        self.assertIn(str(DAILY_CAP), messages[0])
        self.assertIn(str(BADGE_COINS), messages[0])

    def test_source_records_who_gave_it(self):
        user_badge = self._award()

        self.assertIn("curator", user_badge.source)
