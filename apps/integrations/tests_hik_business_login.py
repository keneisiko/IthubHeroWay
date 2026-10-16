"""Вход в бизнес-систему портала Hik.

Обычный логин с 16.10.2026 открывает личный кабинет, и API записей отвечает
«You need login first». Портал открывает бизнес-систему двумя шагами:
спрашивает список систем и переходит на маршрут freeLogin. Здесь проверяется,
что мы повторяем эти шаги и не угадываем за человека, когда систем несколько.
"""

from __future__ import annotations

import json
from unittest import mock

from django.test import TestCase, override_settings

from apps.integrations.services.hik_business_login import (
    BusinessSystem,
    HikBusinessLoginError,
    enter_business_system,
    fetch_business_systems,
    free_login_url,
    hcb_info_url,
    pick_system,
)

SETTINGS = {
    "HIK_WEB_LOGIN_URL": "https://www.hik-connectru.com/views/login/index.html#/login",
    "HIK_WEB_HCB_INFO_PATH": "/customer/proxy/ccfauth/public/user/v1/account/hcb",
    "HIK_WEB_FREE_LOGIN_PATH": "/views/login/index.html#/freeLogin",
}

ONE_SYSTEM = {
    "errorCode": "0",
    "data": {
        "sessionId": "s" * 64,
        "hcbInfoList": [
            {
                "systemId": "3b784c421c34483282bd292d97c6d31d",
                "systemName": "IT Hub",
                "email": "ulbashevkv@nalchik.ithub.ru",
            }
        ],
    },
}


class FakeResponse:
    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self.status = status

    def text(self) -> str:
        return self._payload if isinstance(self._payload, str) else json.dumps(self._payload)


class FakePage:
    """Минимум от страницы Playwright, который нужен коду входа."""

    def __init__(self, payload=ONE_SYSTEM):
        self.request = mock.Mock()
        self.request.post.return_value = FakeResponse(payload)
        self.goto = mock.Mock()
        self.wait_for_timeout = mock.Mock()
        self.wait_for_load_state = mock.Mock()


@override_settings(**SETTINGS)
class UrlTests(TestCase):
    def test_info_url_is_built_from_the_login_origin(self):
        self.assertEqual(
            hcb_info_url(),
            "https://www.hik-connectru.com/customer/proxy/ccfauth/public/user/v1/account/hcb",
        )

    def test_free_login_url_carries_all_required_parameters(self):
        system = BusinessSystem(system_id="sys-1", system_name="IT Hub", account="a@b.ru")

        url = free_login_url(system, "token-123")

        self.assertIn("#/freeLogin?", url)
        self.assertIn("sessionId=token-123", url)
        self.assertIn("chooseTenantId=sys-1", url)
        self.assertIn("account=a%40b.ru", url, "адрес должен быть закодирован")
        self.assertIn("isSimpleBusiness=true", url)

    @override_settings(HIK_WEB_LOGIN_URL="мусор")
    def test_broken_login_url_is_reported(self):
        with self.assertRaises(HikBusinessLoginError):
            hcb_info_url()


@override_settings(**SETTINGS)
class FetchSystemsTests(TestCase):
    def test_reads_session_and_systems(self):
        page = FakePage()

        session_id, systems = fetch_business_systems(page)

        self.assertEqual(len(session_id), 64)
        self.assertEqual([s.system_name for s in systems], ["IT Hub"])
        self.assertEqual(systems[0].account, "ulbashevkv@nalchik.ithub.ru")

    def test_portal_error_is_reported(self):
        page = FakePage({"errorCode": "VMS002004", "message": "You need login first."})

        with self.assertRaises(HikBusinessLoginError) as ctx:
            fetch_business_systems(page)

        self.assertIn("VMS002004", str(ctx.exception))

    def test_non_json_is_reported(self):
        page = FakePage("<html>502</html>")

        with self.assertRaises(HikBusinessLoginError) as ctx:
            fetch_business_systems(page)

        self.assertIn("не JSON", str(ctx.exception))

    def test_account_without_systems_is_reported_clearly(self):
        page = FakePage({"errorCode": "0", "data": {"sessionId": "x", "hcbInfoList": []}})

        with self.assertRaises(HikBusinessLoginError) as ctx:
            fetch_business_systems(page)

        self.assertIn("организацию", str(ctx.exception))

    def test_missing_session_id_is_reported(self):
        page = FakePage(
            {"errorCode": "0", "data": {"hcbInfoList": [{"systemId": "s", "systemName": "n"}]}}
        )

        with self.assertRaises(HikBusinessLoginError):
            fetch_business_systems(page)


@override_settings(**SETTINGS)
class PickSystemTests(TestCase):
    def setUp(self):
        self.first = BusinessSystem("s1", "IT Hub", "a@b.ru")
        self.second = BusinessSystem("s2", "Другая школа", "a@b.ru")

    def test_single_system_is_taken(self):
        self.assertEqual(pick_system([self.first]), self.first)

    def test_several_systems_without_a_choice_stop_the_run(self):
        """Молча взять первую нельзя: забор пошёл бы по чужим проходам."""
        with self.assertRaises(HikBusinessLoginError) as ctx:
            pick_system([self.first, self.second])

        self.assertIn("несколько", str(ctx.exception))

    @override_settings(HIK_WEB_SYSTEM_NAME="другая школа")
    def test_named_system_is_chosen_case_insensitively(self):
        self.assertEqual(pick_system([self.first, self.second]), self.second)

    @override_settings(HIK_WEB_SYSTEM_NAME="Третья")
    def test_unknown_name_lists_what_is_available(self):
        with self.assertRaises(HikBusinessLoginError) as ctx:
            pick_system([self.first, self.second])

        self.assertIn("IT Hub", str(ctx.exception))


@override_settings(**SETTINGS)
class EnterBusinessSystemTests(TestCase):
    def test_navigates_to_free_login_with_the_session(self):
        page = FakePage()

        system = enter_business_system(page)

        self.assertEqual(system.system_name, "IT Hub")
        url = page.goto.call_args[0][0]
        self.assertIn("#/freeLogin?", url)
        self.assertIn("chooseTenantId=3b784c421c34483282bd292d97c6d31d", url)

    def test_slow_network_does_not_fail_the_login(self):
        """Портал догружает модули в фоне — для сессии это не обязательно."""
        page = FakePage()
        page.wait_for_load_state.side_effect = RuntimeError("timeout")

        system = enter_business_system(page)

        self.assertEqual(system.system_id, "3b784c421c34483282bd292d97c6d31d")
