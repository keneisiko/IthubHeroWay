"""Обход всей админки: каждый раздел открывается.

Админка — основной инструмент персонала, и ломается она тихо: ошибка в
autocomplete_fields или list_display всплывает, только когда кто-то
откроет именно этот экран. Тест открывает список, форму добавления и
поиск-автодополнение каждого зарегистрированного раздела.
"""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

User = get_user_model()


# В проде SECURE_SSL_REDIRECT=1, и тестовый клиент получал бы 301 вместо
# страницы — тест проверял бы редирект, а не админку.
@override_settings(SECURE_SSL_REDIRECT=False)
class AdminSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="smoke_admin", password="x", email="smoke@example.com"
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def _registered(self):
        return [
            (model, model_admin)
            for model, model_admin in admin.site._registry.items()
            if model._meta.app_label.startswith(("accounts", "badges", "integrations",
                                                 "progress", "quests", "schedule",
                                                 "shop", "social", "operations"))
        ]

    def test_every_changelist_opens(self):
        broken = []
        for model, _ in self._registered():
            url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
            # follow: у «Настроек платформы» нет списка — сразу единственная запись.
            response = self.client.get(url, follow=True)
            if response.status_code != 200:
                broken.append(f"{model.__name__}: {response.status_code}")
        self.assertEqual(broken, [], "списки, которые не открываются")

    def test_every_search_works(self):
        """Поиск по списку — его используют чаще всего, и он падает отдельно."""
        broken = []
        for model, model_admin in self._registered():
            if not model_admin.search_fields:
                continue
            url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
            response = self.client.get(url, {"q": "иванов"})
            if response.status_code != 200:
                broken.append(f"{model.__name__}: {response.status_code}")
        self.assertEqual(broken, [], "поиск, который падает")

    def test_every_add_form_opens_where_adding_is_allowed(self):
        broken = []
        for model, model_admin in self._registered():
            if not model_admin.has_add_permission(_Request(self.superuser)):
                continue
            try:
                url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_add")
            except NoReverseMatch:
                continue
            response = self.client.get(url)
            if response.status_code != 200:
                broken.append(f"{model.__name__}: {response.status_code}")
        self.assertEqual(broken, [], "формы добавления, которые не открываются")

    def test_autocomplete_targets_are_searchable(self):
        """autocomplete_fields без search_fields у целевой модели — ошибка 403/500
        при первом наборе в поле, а не при старте. Проверяем заранее."""
        broken = []
        for model, model_admin in self._registered():
            for field_name in model_admin.autocomplete_fields:
                field = model._meta.get_field(field_name)
                target = field.remote_field.model
                target_admin = admin.site._registry.get(target)
                if target_admin is None or not target_admin.search_fields:
                    broken.append(f"{model.__name__}.{field_name} -> {target.__name__}")
        self.assertEqual(broken, [], "автопоиск без search_fields у цели")


class _Request:
    def __init__(self, user):
        self.user = user
