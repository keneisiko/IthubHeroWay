from unittest.mock import MagicMock

from django.test import TestCase

from apps.integrations.services.browser_runtime import (
    DEFAULT_LAUNCH_ARGS,
    DEFAULT_USER_AGENT,
    context_kwargs,
    launch_kwargs,
)
from apps.integrations.services.hik_browser_export import _on_login_page


class _FakePage:
    def __init__(self, url: str):
        self.url = url


class LoginDetectionTests(TestCase):
    """Портал — SPA с хешевой маршрутизацией на одном и том же пути.

    До входа:    .../views/login/index.html#/login
    После входа: .../views/login/index.html#/portal

    Путь содержит «/login/» всегда, поэтому проверка по пути считала вход
    неудавшимся навсегда — интеграция падала с «страница логина не сменилась»
    уже после успешной авторизации.
    """

    def test_login_hash_means_still_on_login(self):
        page = _FakePage("https://www.hik-connectru.com/views/login/index.html#/login")
        self.assertTrue(_on_login_page(page))

    def test_portal_hash_means_logged_in_despite_login_in_path(self):
        page = _FakePage("https://www.hik-connectru.com/views/login/index.html#/portal")
        self.assertFalse(_on_login_page(page))

    def test_other_spa_routes_are_logged_in(self):
        for fragment in ("#/accessControl", "#/person", "#/device"):
            page = _FakePage(f"https://www.hik-connectru.com/views/login/index.html{fragment}")
            self.assertFalse(_on_login_page(page), fragment)

    def test_empty_hash_counts_as_login_page(self):
        page = _FakePage("https://www.hik-connectru.com/views/login/index.html#/")
        self.assertTrue(_on_login_page(page))

    def test_path_without_hash_falls_back_to_path_check(self):
        self.assertTrue(_on_login_page(_FakePage("https://example.com/login")))
        self.assertFalse(_on_login_page(_FakePage("https://example.com/dashboard")))


class BrowserRuntimeTests(TestCase):
    """Портал отдаёт заглушку (~1 КБ вместо ~135 КБ), если в user-agent есть
    HeadlessChrome. В контейнере другого режима нет, поэтому подмена UA —
    обязательное условие работоспособности, а не косметика."""

    def test_user_agent_does_not_advertise_headless(self):
        self.assertNotIn("headless", DEFAULT_USER_AGENT.lower())
        self.assertIn("Chrome/", DEFAULT_USER_AGENT)

    def test_context_always_sets_user_agent(self):
        self.assertEqual(context_kwargs()["user_agent"], DEFAULT_USER_AGENT)

    def test_launch_disables_automation_flag(self):
        args = launch_kwargs(headless=True)["args"]
        self.assertIn("--disable-blink-features=AutomationControlled", args)
        for required in DEFAULT_LAUNCH_ARGS:
            self.assertIn(required, args)

    def test_extra_args_are_appended(self):
        args = launch_kwargs(headless=False, extra_args=["--foo"])["args"]
        self.assertIn("--foo", args)
        self.assertFalse(launch_kwargs(headless=False)["headless"])


class NavigationGuardTests(TestCase):
    """Маршрут к записям прохода обязателен.

    Без него скрипт логинился, оставался на главной портала и падал только
    через таймаут ожидания загрузки файла — по сообщению было не понять,
    что дело в пустой настройке.
    """

    def test_missing_route_fails_fast_with_a_clear_message(self):
        from apps.integrations.services.hik_browser_export import (
            HikBrowserExportConfig,
            HikBrowserExportError,
            _navigate_to_records,
        )

        page = MagicMock()
        page.locator.return_value.first.count.return_value = 0
        config = HikBrowserExportConfig(
            login_url="https://example.com",
            email="a@b.c",
            password="x",
            nav_steps=(),
            records_url="",
        )

        with self.assertRaises(HikBrowserExportError) as ctx:
            _navigate_to_records(page, config)

        self.assertIn("HIK_WEB_NAV_STEPS", str(ctx.exception))


class LoginSelectorTests(TestCase):
    """Селекторы полей входа.

    На странице портала ровно одна форма, и поля входа в неё не входят —
    внутри оказывается только поиск по списку регионов. Пока селекторы были
    привязаны к `form`, логин уезжал именно туда: поле «Account/Email»
    оставалось пустым, а адрес почты появлялся в выборе региона.
    """

    def test_selectors_are_not_bound_to_form(self):
        from apps.integrations.services.hik_browser_export import ACCOUNT_SELECTORS

        for selector in ACCOUNT_SELECTORS:
            self.assertFalse(selector.startswith("form "), selector)

    def test_fallback_excludes_dropdown_inputs(self):
        """Запасной селектор не должен цеплять строки выбора региона и языка."""
        from apps.integrations.services.hik_browser_export import ACCOUNT_SELECTORS

        fallback = ACCOUNT_SELECTORS[-1]
        self.assertIn(":not([readonly])", fallback)
        self.assertIn("Select", fallback)

    def test_account_value_reads_visible_field(self):
        from apps.integrations.services.hik_browser_export import _account_value

        page = MagicMock()
        field = page.locator.return_value.first
        field.count.return_value = 1
        field.is_visible.return_value = True
        field.input_value.return_value = "  user@nalchik.ithub.ru "

        self.assertEqual(_account_value(page), "user@nalchik.ithub.ru")
