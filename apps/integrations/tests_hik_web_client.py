"""Тесты клиента внутреннего API портала Hik Connect.

Записи в фикстурах повторяют реальную форму ответа портала, снятую с живой
сессии: пустой cardNumber, personInfo.baseInfo с email и personCode,
direction 1/2, occurTime в UTC и deviceTime со смещением.
"""

from datetime import datetime
from unittest.mock import Mock

import requests
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.integrations.services.hik_web_client import (
    DIRECTION_ENTRY,
    DIRECTION_EXIT,
    HikWebAuthError,
    HikWebClient,
    HikWebClientError,
    HikWebConfig,
    build_search_payload,
    normalize_record,
)


def make_record(**overrides) -> dict:
    record = {
        "recordGuid": "guid-001",
        "elementName": "Вход F-KD-3323PMFC(GA4818572)",
        "deviceName": "Вход F-KD-3323PMFC(GA4818572)",
        "cardReaderName": "GA4818572-Cardreader 01",
        "occurTime": "2026-06-29T16:05:46Z",
        "deviceTime": "2026-06-29T19:05:46+03:00",
        "recordTime": "2026-06-29T16:05:50Z",
        "eventType": 110013,
        "swipeAuthResult": 1,
        "direction": DIRECTION_ENTRY,
        "cardNumber": "",
        "personInfo": {
            "id": "person-42",
            "baseInfo": {
                "personCode": "STU-42",
                "email": "Ivanov@nalchik.ithub.ru",
                "firstName": "Иван",
                "lastName": "Иванов",
                "personType": 1,
            },
        },
    }
    record.update(overrides)
    return record


def make_config() -> HikWebConfig:
    return HikWebConfig(
        base_url="https://team.example.com",
        records_path="/hcc/hccacs/v1/event/certificateRecords/search",
        page_size=2,
        timeout=5,
    )


def make_response(status: int = 200, payload: dict | None = None) -> Mock:
    response = Mock()
    response.status_code = status
    response.json.return_value = payload if payload is not None else {}
    return response


class NormalizeRecordTests(TestCase):
    def test_uses_portal_guid_as_event_id(self):
        """recordGuid стабилен, поэтому самодельные хеши больше не нужны."""
        row = normalize_record(make_record())
        self.assertEqual(row["eventId"], "guid-001")

    def test_person_is_identified_by_email_and_code(self):
        """cardNumber на портале пуст всегда — связывать приходится по почте."""
        row = normalize_record(make_record())
        self.assertEqual(row["cardNumber"], "")
        self.assertEqual(row["personEmail"], "ivanov@nalchik.ithub.ru")
        self.assertEqual(row["personCode"], "STU-42")
        self.assertEqual(row["personId"], "person-42")
        self.assertEqual(row["personName"], "Иванов Иван")

    def test_entry_and_exit_are_distinguished(self):
        self.assertTrue(normalize_record(make_record())["isEntry"])
        exit_row = normalize_record(make_record(direction=DIRECTION_EXIT))
        self.assertFalse(exit_row["isEntry"])
        self.assertEqual(exit_row["direction"], DIRECTION_EXIT)

    def test_prefers_local_device_time_over_utc(self):
        """deviceTime уже со смещением; occurTime в UTC — берём первое."""
        row = normalize_record(make_record())
        self.assertEqual(row["eventTime"], "2026-06-29T19:05:46+03:00")

    def test_falls_back_to_occur_time(self):
        row = normalize_record(make_record(deviceTime=""))
        self.assertEqual(row["eventTime"], "2026-06-29T16:05:46Z")

    def test_failed_swipe_is_marked(self):
        self.assertTrue(normalize_record(make_record())["authOk"])
        self.assertFalse(normalize_record(make_record(swipeAuthResult=0))["authOk"])

    def test_record_without_guid_is_skipped(self):
        self.assertIsNone(normalize_record(make_record(recordGuid="")))

    def test_record_without_any_time_is_skipped(self):
        self.assertIsNone(normalize_record(make_record(deviceTime="", occurTime="")))

    def test_record_without_person_does_not_crash(self):
        row = normalize_record(make_record(personInfo=None))
        self.assertEqual(row["personEmail"], "")
        self.assertEqual(row["personCode"], "")


class SearchPayloadTests(TestCase):
    def test_payload_matches_portal_contract(self):
        start = timezone.make_aware(datetime(2026, 6, 1, 0, 0, 0))
        end = timezone.make_aware(datetime(2026, 6, 1, 23, 59, 59))
        payload = build_search_payload(start, end, page=2, page_size=50)

        self.assertEqual(payload["pageIndex"], 2)
        self.assertEqual(payload["pageSize"], 50)
        criteria = payload["searchCriteria"]
        self.assertIn("+03:00", criteria["beginTime"])
        self.assertEqual(criteria["personCondition"], {})
        self.assertEqual(criteria["swipeAuthResult"], 0)

    def test_naive_datetime_is_rejected(self):
        """Без таймзоны портал молча вернёт не тот диапазон."""
        with self.assertRaises(ValueError):
            build_search_payload(
                datetime(2026, 6, 1), datetime(2026, 6, 2), page=1, page_size=10
            )


@override_settings(HIK_WEB_API_BASE="https://team.example.com")
class HikWebClientTests(TestCase):
    def setUp(self):
        self.start = timezone.make_aware(datetime(2026, 6, 1, 0, 0, 0))
        self.end = timezone.make_aware(datetime(2026, 6, 30, 23, 59, 59))

    def _client(self, responses: list[Mock]) -> tuple[HikWebClient, Mock]:
        session = Mock()
        session.cookies = Mock()
        session.post.side_effect = responses
        return HikWebClient({"sid": "x"}, config=make_config(), session=session), session

    def test_pages_until_all_records_collected(self):
        page1 = make_response(payload={
            "errorCode": "0",
            "data": {"totalNum": 3, "recordList": [make_record(recordGuid="g1"), make_record(recordGuid="g2")]},
        })
        page2 = make_response(payload={
            "errorCode": "0",
            "data": {"totalNum": 3, "recordList": [make_record(recordGuid="g3")]},
        })
        client, session = self._client([page1, page2])

        rows = client.fetch_rows(self.start, self.end)

        self.assertEqual([r["eventId"] for r in rows], ["g1", "g2", "g3"])
        self.assertEqual(session.post.call_count, 2)
        self.assertEqual(session.post.call_args_list[1].kwargs["json"]["pageIndex"], 2)

    def test_empty_range_returns_nothing_without_error(self):
        """Каникулы и выключенные турникеты — это ноль записей, а не ошибка."""
        client, _ = self._client([
            make_response(payload={"errorCode": "0", "data": {"totalNum": 0, "recordList": []}})
        ])
        self.assertEqual(client.fetch_rows(self.start, self.end), [])

    def test_expired_session_raises_auth_error(self):
        client, _ = self._client([make_response(status=401)])
        with self.assertRaises(HikWebAuthError):
            client.fetch_rows(self.start, self.end)

    def test_session_expiry_reported_in_body_is_auth_error(self):
        """Портал умеет сообщать об истёкшей сессии кодом при HTTP 200."""
        client, _ = self._client([
            make_response(payload={"errorCode": "10002", "message": "Login timed out. Try again."})
        ])
        with self.assertRaises(HikWebAuthError):
            client.fetch_rows(self.start, self.end)

    def test_other_error_code_is_client_error(self):
        client, _ = self._client([
            make_response(payload={"errorCode": "500", "message": "internal"})
        ])
        with self.assertRaises(HikWebClientError):
            client.fetch_rows(self.start, self.end)

    def test_network_failure_is_wrapped(self):
        session = Mock()
        session.cookies = Mock()
        session.post.side_effect = requests.ConnectionError("boom")
        client = HikWebClient({}, config=make_config(), session=session)
        with self.assertRaises(HikWebClientError):
            client.fetch_rows(self.start, self.end)

    def test_missing_base_url_fails_loudly(self):
        with override_settings(HIK_WEB_API_BASE=""):
            with self.assertRaises(HikWebClientError):
                HikWebClient({}, config=HikWebConfig("", "/x", 10, 5))
