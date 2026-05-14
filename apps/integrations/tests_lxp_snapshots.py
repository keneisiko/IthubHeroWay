from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.integrations.models import LXPSnapshot
from apps.integrations.services.lxp_graphql_client import LXPGraphQLClient
from apps.integrations.services.lxp_snapshot_reader import NoSnapshotAvailable, get_latest_snapshot


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "test-locmem"}},
    LXP_GRAPHQL_ENDPOINT="https://example.test/graphql",
    LXP_BOT_EMAIL="bot@example.test",
    LXP_BOT_PASSWORD="secret",
    LXP_TOKEN_TTL_SECONDS=3600,
    # Иначе из .env подтягивается браузерный бот — мок requests.post не сработает.
    LXP_USE_BROWSER_TOKEN_BOT=False,
    LXP_API_TOKEN="",
)
class LXPSnapshotTests(TestCase):
    def test_snapshot_fallback(self):
        with self.assertRaises(NoSnapshotAvailable):
            get_latest_snapshot()

        d1 = date.today() - timedelta(days=2)
        d2 = date.today() - timedelta(days=1)
        LXPSnapshot.objects.create(date=d1, data={"x": 1})
        LXPSnapshot.objects.create(date=d2, data={"x": 2})

        self.assertEqual(get_latest_snapshot().date, d2)
        self.assertEqual(get_latest_snapshot(prefer_date=d1).date, d1)
        self.assertEqual(get_latest_snapshot(prefer_date=date.today()).date, d2)

    @patch("apps.integrations.services.lxp_graphql_client.requests.post")
    def test_token_cached(self, post):
        cache.clear()
        # First call: login returns token
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"data": {"login": {"token": "t1"}}}

        client = LXPGraphQLClient()
        t1 = client.get_token()
        self.assertEqual(t1, "t1")

        # Second call: must come from cache, so requests.post not called again for login.
        post.reset_mock()
        t2 = client.get_token()
        self.assertEqual(t2, "t1")
        post.assert_not_called()


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "test-lxp-fetch"}},
    LXP_GRAPHQL_ENDPOINT="https://example.test/graphql",
    LXP_BOT_EMAIL="bot@example.test",
    LXP_BOT_PASSWORD="secret",
    LXP_TOKEN_TTL_SECONDS=3600,
    LXP_USE_BROWSER_TOKEN_BOT=False,
    LXP_API_TOKEN="",
)
class LXPGraphQLFetchAllDataTests(TestCase):
    """fetch_all_data без сети: патчим внутренние сборщики данных."""

    def test_fetch_all_data_ok_not_partial(self):
        with (
            patch.object(LXPGraphQLClient, "get_token", return_value="tok"),
            patch.object(
                LXPGraphQLClient,
                "_fetch_learning_groups_performance",
                return_value={
                    "me_query_ok": True,
                    "assigned_suborganizations_count": 0,
                    "ok": True,
                    "grades": {},
                    "control_points": {},
                    "discipline_attendance": {},
                    "groups_processed": 0,
                    "errors": [],
                },
            ),
            patch.object(
                LXPGraphQLClient,
                "_fetch_students_performance",
                return_value={
                    "ok": True,
                    "data": {
                        "attendance": {"u1": {"has_attendance": True}},
                        "course_progress": {"u1": {"is_learning": True}},
                        "students_total_loaded": 1,
                        "students_pages_loaded": 1,
                    },
                },
            ),
        ):
            payload = LXPGraphQLClient().fetch_all_data(date=date.today())
        self.assertFalse(payload["meta"]["partial"])
        self.assertTrue(payload["grades"]["ok"])
        self.assertIn("u1", payload["attendance"]["data"])

    def test_fetch_all_data_partial_when_catalog_me_fails(self):
        with (
            patch.object(LXPGraphQLClient, "get_token", return_value="tok"),
            patch.object(
                LXPGraphQLClient,
                "_fetch_learning_groups_performance",
                return_value={
                    "me_query_ok": False,
                    "assigned_suborganizations_count": 0,
                    "ok": False,
                    "error": "GraphQL boom",
                    "grades": {},
                    "control_points": {},
                    "discipline_attendance": {},
                    "groups_processed": 0,
                    "errors": ["getMe failed"],
                },
            ),
            patch.object(
                LXPGraphQLClient,
                "_fetch_students_performance",
                return_value={"ok": True, "data": {"attendance": {}, "course_progress": {}, "students_total_loaded": 0, "students_pages_loaded": 1}},
            ),
        ):
            payload = LXPGraphQLClient().fetch_all_data(date=date.today())
        self.assertTrue(payload["meta"]["partial"])
        self.assertFalse(payload["grades"]["ok"])

