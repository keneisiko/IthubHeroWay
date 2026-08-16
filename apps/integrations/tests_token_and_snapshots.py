"""Тесты на места, где данные портились молча.

Общее у всех трёх: ошибка не падала наружу, а тихо приводила к неверным
данным — протухший токен, затёртый снимок, вечно перечитываемое событие.
"""

from datetime import date, datetime
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.integrations.models import HikEvent, HikSnapshot
from apps.integrations.services.hik_attendance_processor import (
    MAX_PROCESS_ATTEMPTS,
    process_unprocessed_hik_events,
)
from apps.integrations.services.hik_snapshot_service import save_hik_snapshot
from apps.integrations.services.lxp_graphql_client import LXPGraphQLClient, LXPRequestError

User = get_user_model()


@override_settings(LXP_GRAPHQL_ENDPOINT="https://api.example.com/graphql", LXP_API_TOKEN="")
class TokenCacheTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_cached_token_is_reused_without_login(self):
        cache.set(LXPGraphQLClient.TOKEN_CACHE_KEY, "cached-token", 3600)
        client = LXPGraphQLClient()

        with patch.object(LXPGraphQLClient, "login") as login:
            self.assertEqual(client.get_token(), "cached-token")
        login.assert_not_called()

    def test_static_token_wins_over_login(self):
        """При заданном LXP_API_TOKEN вход не нужен вовсе — раньше
        refresh_lxp_token_sync всё равно шёл логиниться и падал без пароля."""
        with override_settings(LXP_API_TOKEN="static-token"):
            client = LXPGraphQLClient()
            with patch.object(LXPGraphQLClient, "login") as login:
                self.assertEqual(client.get_token(), "static-token")
            login.assert_not_called()

    def test_lock_prevents_parallel_login(self):
        """Промах кеша у нескольких воркеров приводил к нескольким входам
        подряд (а в браузерном режиме — к нескольким Chromium)."""
        client = LXPGraphQLClient()
        # Лок занят другим процессом, а токен появляется сразу после.
        cache.set(LXPGraphQLClient.TOKEN_LOCK_KEY, "1", 60)
        cache.set(LXPGraphQLClient.TOKEN_CACHE_KEY, "token-from-other-worker", 3600)

        with patch.object(LXPGraphQLClient, "login") as login:
            self.assertEqual(client.get_token(), "token-from-other-worker")
        login.assert_not_called()

    @patch("apps.integrations.services.lxp_graphql_client.requests.post")
    def test_rejected_token_is_dropped_from_cache(self, post):
        """Протухший токен оставался в кеше почти сутки, и все запросы
        за это время получали 401, а снимки сохранялись пустыми."""
        cache.set(LXPGraphQLClient.TOKEN_CACHE_KEY, "stale-token", 3600)
        response = Mock()
        response.status_code = 401
        response.text = "unauthorized"
        post.return_value = response

        client = LXPGraphQLClient()
        with self.assertRaises(LXPRequestError):
            client._post("query { me { id } }", token="stale-token")

        self.assertIsNone(cache.get(LXPGraphQLClient.TOKEN_CACHE_KEY))

    def test_refresh_token_is_not_stored(self):
        """refresh-токен клался в Redis и не читался нигде: мутации обновления
        в клиенте нет. Лишний секрет в кеше — только риск."""
        self.assertIsNone(cache.get(f"{LXPGraphQLClient.TOKEN_CACHE_KEY}_refresh"))


class HikSnapshotOverwriteTests(TestCase):
    def _payload(self, events: int) -> dict:
        return {
            "date": "2026-06-15",
            "events": [
                {
                    "eventId": f"e{i}",
                    "personCode": "CARD-1",
                    "eventTime": "2026-06-15T09:00:00+03:00",
                    "eventType": "access",
                    "doorName": "Вход",
                }
                for i in range(events)
            ],
        }

    def test_empty_export_does_not_erase_existing_snapshot(self):
        """Неудачная выгрузка стирала валидные данные за день, при том что
        созданные из них HikEvent оставались — состояние расходилось."""
        target = date(2026, 6, 15)
        save_hik_snapshot(target, self._payload(3))

        save_hik_snapshot(target, self._payload(0))

        snap = HikSnapshot.objects.get(date=target)
        self.assertEqual(len(snap.data["events"]), 3)

    def test_force_allows_deliberate_reset(self):
        target = date(2026, 6, 15)
        save_hik_snapshot(target, self._payload(3))

        save_hik_snapshot(target, self._payload(0), force=True)

        self.assertEqual(len(HikSnapshot.objects.get(date=target).data["events"]), 0)

    def test_non_empty_export_replaces_previous(self):
        target = date(2026, 6, 15)
        save_hik_snapshot(target, self._payload(1))
        save_hik_snapshot(target, self._payload(5))
        self.assertEqual(len(HikSnapshot.objects.get(date=target).data["events"]), 5)


class FailedEventQuarantineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="agent",
            email="a@test.ru",
            password="x",
            callsign="agent_call",
            hik_card_code="CARD-Q",
        )
        HikEvent.objects.create(
            event_id="broken-1",
            student_code="CARD-Q",
            event_time=timezone.make_aware(datetime(2026, 6, 15, 9, 0)),
            event_type="access",
            door_name="Вход",
            raw_data={},
        )

    @patch("apps.integrations.services.hik_attendance_processor.classify_entrance_against_schedule")
    def test_failing_event_is_quarantined_after_attempts(self, classify):
        """Событие, на котором обработчик падает, не помечалось обработанным
        и перечитывалось на каждом прогоне вечно."""
        classify.side_effect = RuntimeError("boom")

        for _ in range(MAX_PROCESS_ATTEMPTS):
            process_unprocessed_hik_events(limit=10)

        event = HikEvent.objects.get(event_id="broken-1")
        self.assertEqual(event.process_attempts, MAX_PROCESS_ATTEMPTS)
        self.assertTrue(event.processed, "после исчерпания попыток событие уходит в карантин")
        self.assertIn("boom", event.last_error)

    @patch("apps.integrations.services.hik_attendance_processor.classify_entrance_against_schedule")
    def test_event_is_retried_before_quarantine(self, classify):
        classify.side_effect = RuntimeError("boom")

        process_unprocessed_hik_events(limit=10)

        event = HikEvent.objects.get(event_id="broken-1")
        self.assertEqual(event.process_attempts, 1)
        self.assertFalse(event.processed, "одной неудачи недостаточно для карантина")
