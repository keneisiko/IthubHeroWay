"""Кнопка «Обнулить данные студентов» в настройках платформы."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.badges.models import AvatarFrame, Badge, UserBadge
from apps.operations.models import PlatformSettings
from apps.operations.services.platform_settings import invalidate

URL = "admin:operations_platformsettings_reset"


def set_accruals(enabled: bool) -> None:
    PlatformSettings.objects.update_or_create(
        pk=PlatformSettings.SINGLETON_PK, defaults={"accruals_enabled": enabled}
    )
    invalidate()


class ResetButtonTests(TestCase):
    def setUp(self):
        set_accruals(False)
        self.root = User.objects.create_superuser(
            username="root", password="x", callsign="root", role=Role.ADMIN
        )
        self.student = User.objects.create_user(
            username="s1", password="x", callsign="s1", role=Role.AGENT,
            rating_current=Decimal("5"), coins_balance=Decimal("3"), is_active=True,
        )
        self.dev = Badge.objects.create(code="dev", title="Разработчик", avatar_frame=AvatarFrame.DEVELOPER)
        self.other = Badge.objects.create(code="other", title="Другая")
        UserBadge.objects.create(user=self.student, badge=self.dev)
        UserBadge.objects.create(user=self.student, badge=self.other)

    def post(self, word: str, students: int = 1):
        return self.client.post(reverse(URL), {"confirm": word, "students": students})

    def test_superadmin_resets_and_developer_badge_stays(self):
        self.client.force_login(self.root)
        self.post("обнулить")
        self.student.refresh_from_db()
        self.assertEqual(self.student.rating_current, 0)
        self.assertEqual(self.student.coins_balance, 0)
        self.assertFalse(self.student.is_active)
        self.assertEqual(
            list(UserBadge.objects.values_list("badge__code", flat=True)), ["dev"]
        )

    def test_wrong_word_changes_nothing(self):
        self.client.force_login(self.root)
        self.post("да")
        self.student.refresh_from_db()
        self.assertEqual(self.student.rating_current, 5)

    def test_refused_while_accruals_on(self):
        set_accruals(True)
        self.client.force_login(self.root)
        self.post("ОБНУЛИТЬ")
        self.student.refresh_from_db()
        self.assertEqual(self.student.rating_current, 5)

    def test_stale_student_count_refused(self):
        self.client.force_login(self.root)
        self.post("ОБНУЛИТЬ", students=99)
        self.student.refresh_from_db()
        self.assertEqual(self.student.rating_current, 5)

    def test_non_superuser_admin_forbidden(self):
        admin_user = User.objects.create_user(
            username="adm", password="x", callsign="adm", role=Role.ADMIN, is_staff=True
        )
        self.client.force_login(admin_user)
        self.assertEqual(self.post("ОБНУЛИТЬ").status_code, 403)
        self.student.refresh_from_db()
        self.assertEqual(self.student.rating_current, 5)

    def test_confirmation_page_renders(self):
        self.client.force_login(self.root)
        response = self.client.get(reverse(URL))
        self.assertContains(response, "ОБНУЛИТЬ")
