"""Открытие бизнес-системы портала Hik.

С 16.10.2026 обычный логин открывает личный кабинет, и API записей отвечает
«You need login first». Сессию открывает страница портала: загружаясь, она
вызывает loginafter на домене API. Поэтому готовность проверяется делом —
ответом самого API, а не видом страницы: портал выглядит по-разному даже
между двумя запусками подряд.
"""

from __future__ import annotations

import json
from unittest import mock

from django.test import TestCase, override_settings

from apps.integrations.services.hik_business_login import (
    BusinessSystem,
    HikBusinessLoginError,
    ensure_business_session,
    fetch_business_systems,
    free_login_url,
    hcb_info_url,
    pick_system,
    portal_url,
    session_is_ready,
)

SETTINGS = {
    "HIK_WEB_LOGIN_URL": "https://www.hik-connectru.com/views/login/index.html#/login",
    "HIK_WEB_HCB_INFO_PATH": "/customer/proxy/ccfauth/public/user/v1/account/hcb",
    "HIK_WEB_FREE_LOGIN_PATH": "/views/login/index.html#/freeLogin",
    "HIK_WEB_PORTAL_PATH": "/views/login/index.html#/portal",
    "HIK_WEB_API_BASE": "https://team.hikcentralconnectru.com",
    "HIK_WEB_API_RECORDS_PATH": "/hcc/hccacs/v1/event/certificateRecords/search",
    "HIK_WEB_SYSTEM_NAME": "",
}

NOT_LOGGED_IN = {"errorCode": "VMS002004", "message": "You need login first."}
RECORDS_OK = {"errorCode": "0", "message": "Ok", "data": {"totalNum": 1116, "recordList": []}}
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
    def __init__(self, payload):
        self._payload = payload
        self.status = 200

    def text(self) -> str:
        return self._payload if isinstance(self._payload, str) else json.dumps(self._payload)


class FakePage:
    """Страница портала, отвечающая по сценарию.

    `records` — очередь ответов API записей: так описывается «сначала не
    пускало, после открытия портала пустило».
    """

    def __init__(self, records: list, systems=ONE_SYSTEM):
        self.records = list(records)
        self.systems = systems
        self.opened: list[str] = []
        self.request = mock.Mock()
        self.request.post.side_effect = self._post
        self.wait_for_timeout = mock.Mock()
        self.wait_for_load_state = mock.Mock()

    def goto(self, url, **kwargs):
        self.opened.append(url)

    def _post(self, url, **kwargs):
        if "account/hcb" in url:
            return FakeResponse(self.systems)
        if self.records:
            return FakeResponse(self.records.pop(0))
        return FakeResponse(NOT_LOGGED_IN)


@override_settings(**SETTINGS)
class UrlTests(TestCase):
    def test_urls_are_built_from_the_login_origin(self):
        self.assertEqual(
            hcb_info_url(),
            "https://www.hik-connectru.com/customer/proxy/ccfauth/public/user/v1/account/hcb",
        )
        self.assertEqual(
            portal_url(), "https://www.hik-connectru.com/views/login/index.html#/portal"
        )

    def test_free_login_url_carries_all_parameters(self):
        url = free_login_url(BusinessSystem("sys-1", "IT Hub", "a@b.ru"), "token-123")

        self.assertIn("#/freeLogin?", url)
        self.assertIn("sessionId=token-123", url)
        self.assertIn("chooseTenantId=sys-1", url)
        self.assertIn("account=a%40b.ru", url, "адрес должен быть закодирован")

    @override_settings(HIK_WEB_LOGIN_URL="мусор")
    def test_broken_login_url_is_reported(self):
        with self.assertRaises(HikBusinessLoginError):
            hcb_info_url()


@override_settings(**SETTINGS)
class ReadinessTests(TestCase):
    def test_zero_error_code_means_ready(self):
        self.assertTrue(session_is_ready(FakePage([RECORDS_OK])))

    def test_need_login_means_not_ready(self):
        self.assertFalse(session_is_ready(FakePage([NOT_LOGGED_IN])))

    def test_unexpected_code_is_not_ready(self):
        page = FakePage([{"errorCode": "VMS000001", "message": "Param Error"}])

        self.assertFalse(session_is_ready(page))

    def test_timeout_is_not_ready(self):
        page = FakePage([])
        page.request.post.side_effect = TimeoutError("портал молчит")

        self.assertFalse(session_is_ready(page))

    def test_non_json_is_not_ready(self):
        self.assertFalse(session_is_ready(FakePage(["<html>502</html>"])))


@override_settings(**SETTINGS)
class EnsureSessionTests(TestCase):
    def test_ready_session_opens_nothing(self):
        page = FakePage([RECORDS_OK])

        ensure_business_session(page)

        self.assertEqual(page.opened, [], "лишний раз портал не дёргаем")

    def test_portal_page_opens_the_session(self):
        """Обычный путь: страница портала сама вызывает loginafter."""
        page = FakePage([NOT_LOGGED_IN, RECORDS_OK])


        ensure_business_session(page)

        self.assertEqual(len(page.opened), 1)
        self.assertIn("#/portal", page.opened[0])

    def test_free_login_is_the_fallback(self):
        """Запасной путь — когда страница портала не подняла сессию.

        Проверка идёт один раз до открытия портала и затем READY_ATTEMPTS
        раз после: пока они не исчерпаны, до freeLogin дело не доходит.
        """
        from apps.integrations.services.hik_business_login import READY_ATTEMPTS

        page = FakePage([NOT_LOGGED_IN] * (READY_ATTEMPTS + 1) + [RECORDS_OK])

        ensure_business_session(page)

        self.assertEqual(len(page.opened), 2)
        self.assertIn("#/portal", page.opened[0])
        self.assertIn("#/freeLogin", page.opened[1])
        self.assertIn("chooseTenantId=3b784c421c34483282bd292d97c6d31d", page.opened[1])

    def test_failure_names_the_system_and_points_to_the_doc(self):
        page = FakePage([NOT_LOGGED_IN] * 40)

        with self.assertRaises(HikBusinessLoginError) as ctx:
            ensure_business_session(page)

        message = str(ctx.exception)
        self.assertIn("IT Hub", message)
        self.assertIn("HIKCENTRAL.md", message)

    def test_account_without_session_id_is_reported(self):
        page = FakePage([NOT_LOGGED_IN, NOT_LOGGED_IN], systems={"errorCode": "0", "data": {}})

        with self.assertRaises(HikBusinessLoginError) as ctx:
            ensure_business_session(page)

        self.assertIn("sessionId", str(ctx.exception))


@override_settings(**SETTINGS)
class FetchSystemsTests(TestCase):
    def test_reads_session_and_systems(self):
        session_id, systems = fetch_business_systems(FakePage([]))

        self.assertEqual(len(session_id), 64)
        self.assertEqual([s.system_name for s in systems], ["IT Hub"])

    def test_portal_error_is_reported(self):
        page = FakePage([], systems=NOT_LOGGED_IN)

        with self.assertRaises(HikBusinessLoginError) as ctx:
            fetch_business_systems(page)

        self.assertIn("VMS002004", str(ctx.exception))

    def test_account_without_systems_is_reported(self):
        page = FakePage(
            [], systems={"errorCode": "0", "data": {"sessionId": "x", "hcbInfoList": []}}
        )

        with self.assertRaises(HikBusinessLoginError) as ctx:
            fetch_business_systems(page)

        self.assertIn("организацию", str(ctx.exception))


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
class DiagnosticsTests(TestCase):
    """Ошибка должна объяснять, что ответил портал."""

    def test_missing_session_id_shows_what_came_back(self):
        page = FakePage(
            [NOT_LOGGED_IN] * 40,
            systems={"errorCode": "0", "data": {"hcbInfoList": [], "tip": "no tenant"}},
        )

        with self.assertRaises(HikBusinessLoginError) as ctx:
            ensure_business_session(page)

        message = str(ctx.exception)
        self.assertIn("sessionId", message)
        self.assertIn("Портал ответил", message, "без текста ответа это тупик")
        self.assertIn("hcbInfoList", message)

    def test_long_values_are_masked(self):
        from apps.integrations.services.hik_business_login import _describe

        shown = _describe({"sessionId": "x" * 300, "short": "ok"})

        self.assertEqual(shown["short"], "ok")
        self.assertIn("знаков", shown["sessionId"])
