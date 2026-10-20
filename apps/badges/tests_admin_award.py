"""Выдача нашивки вручную через админку.

Часть нашивок автомат выдать не может: «Стажировка» и «Выпуск» платформа
сама не узнаёт. Руководство персонала описывало экран «Значки пользователей
→ Добавить», но добавление было запрещено с первого коммита админки — кнопки
не существовало, и выдать такую нашивку было нельзя ничем, кроме shell.
"""

from __future__ import annotations

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.accounts.models import Role
from apps.badges.admin import UserBadgeAdmin
from apps.badges.models import Badge, UserBadge

User = get_user_model()


class _Request:
    """Запрос с минимумом, который нужен save_model: пользователь и messages."""

    def __init__(self, user):
        self.user = user
        self._messages: list[str] = []


class UserBadgeAdminAwardTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = UserBadgeAdmin(UserBadge, self.site)
        self.staff = User.objects.create_user(
            username="curator", password="x", role=Role.CURATOR, is_staff=True
        )
        self.agent = User.objects.create_user(
            username="agent_badge", password="x", callsign="agent_badge", role=Role.AGENT
        )
        self.badge = Badge.objects.create(
            code="path-internship",
            title="Стажировка",
            reward_coins=50,
            is_active=True,
        )
        self.request = RequestFactory().post("/admin/")
        self.request.user = self.staff

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
        """Иначе выданная руками нашивка отличалась бы от автоматической."""
        before = self.agent.coins_balance

        self._award()

        self.agent.refresh_from_db()
        self.assertEqual(self.agent.coins_balance, before + 50)

    def test_source_records_who_gave_it(self):
        user_badge = self._award()

        self.assertIn("curator", user_badge.source)
