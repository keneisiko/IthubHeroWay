"""Настройки платформы, которые правит персонал.

Главное, что здесь проверяется: значение из админки действительно меняет
поведение, и меняет сразу. Экран, правка на котором ни на что не влияет,
хуже его отсутствия — сотрудник уверен, что поменял.
"""

from __future__ import annotations

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Role
from apps.operations.admin import PlatformSettingsAdmin
from apps.operations.models import PlatformSettings
from apps.operations.services.platform_settings import invalidate, platform_setting
from apps.progress.services.rewards import grant_coins_with_daily_cap

User = get_user_model()


class PlatformSettingsTestCase(TestCase):
    def setUp(self):
        # Откат транзакции после теста возвращает строку, но не кеш.
        invalidate()
        self.addCleanup(invalidate)


class DefaultsTests(PlatformSettingsTestCase):
    def test_migration_keeps_current_values(self):
        """После миграции поведение не меняется: те же числа, что были в коде."""
        self.assertEqual(platform_setting("max_daily_coins"), 10)
        self.assertEqual(platform_setting("ct_scope"), "deferred")

    def test_unknown_name_fails_loudly(self):
        """Опечатка не должна тихо давать None, который станет нулём монет."""
        with self.assertRaises(KeyError):
            platform_setting("max_daly_coins")

    def test_only_one_row_exists(self):
        PlatformSettings.objects.get().save()
        another = PlatformSettings.objects.get()
        another.pk = None
        another.save()

        self.assertEqual(PlatformSettings.objects.count(), 1)


class TakesEffectTests(PlatformSettingsTestCase):
    def setUp(self):
        super().setUp()
        self.agent = User.objects.create_user(
            username="agent_cap", password="x", callsign="agent_cap", role=Role.AGENT
        )

    def test_new_cap_applies_immediately(self):
        """Без сброса кеша новый предел заработал бы только через 5 минут."""
        platform_setting("max_daily_coins")  # прогреть кеш старым значением
        row = PlatformSettings.objects.get()
        row.max_daily_coins = 40
        row.save()

        granted = grant_coins_with_daily_cap(self.agent, 50)

        self.assertEqual(granted, 40)

    @override_settings(RATING_LIMITS={"MAX_DAILY_COINS": 7})
    def test_override_settings_still_reaches_the_code(self):
        """Десятки тестов подменяют RATING_LIMITS — подмена должна доходить."""
        self.assertEqual(platform_setting("max_daily_coins"), 7)


@override_settings(SECURE_SSL_REDIRECT=False)
class AdminScreenTests(PlatformSettingsTestCase):
    def setUp(self):
        super().setUp()
        self.admin_user = User.objects.create_user(
            username="boss", password="x", callsign="boss", role=Role.ADMIN, is_staff=True
        )
        self.curator = User.objects.create_user(
            username="curator_ro", password="x", callsign="curator_ro", role=Role.CURATOR, is_staff=True
        )
        self.model_admin = PlatformSettingsAdmin(PlatformSettings, AdminSite())

    def test_list_goes_straight_to_the_single_row(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:operations_platformsettings_changelist"))

        self.assertRedirects(
            response,
            reverse("admin:operations_platformsettings_change", args=[PlatformSettings.SINGLETON_PK]),
        )

    def test_only_admins_can_change(self):
        """От этих чисел зависят монеты всех студентов сразу."""

        class Req:
            def __init__(self, user):
                self.user = user

        self.assertTrue(self.model_admin.has_change_permission(Req(self.admin_user)))
        self.assertFalse(self.model_admin.has_change_permission(Req(self.curator)))

    def test_history_shows_old_and_new_value(self):
        """«Изменено: дневной предел» не объясняет, почему монет стало меньше."""
        self.client.force_login(self.admin_user)
        url = reverse("admin:operations_platformsettings_change", args=[PlatformSettings.SINGLETON_PK])
        page = self.client.get(url)
        form_data = {
            name: value
            for name, value in page.context["adminform"].form.initial.items()
            if value is not None
        }
        form_data["max_daily_coins"] = 25

        self.client.post(url, {k: ("on" if v is True else v) for k, v in form_data.items() if v is not False})

        from django.contrib.admin.models import LogEntry

        entry = LogEntry.objects.filter(object_id=str(PlatformSettings.SINGLETON_PK)).latest("action_time")
        message = entry.get_change_message()
        self.assertIn("10", message)
        self.assertIn("25", message)
        self.assertIn("→", message)
