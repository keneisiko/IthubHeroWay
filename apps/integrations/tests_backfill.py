from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.integrations.services.lxp_graphql_client import GraphQLResponse


def _single_page(items: list[dict]) -> GraphQLResponse:
    return GraphQLResponse(
        data={"searchStudents": {"items": items, "totalPages": 1, "hasMore": False}},
        errors=None,
    )


class BackfillLxpUserIdsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="agent1", password="x", callsign="agent1", email="agent1@nalchik.ithub.ru"
        )
        self.page = _single_page([{"user": {"id": "lxp-100", "email": "agent1@nalchik.ithub.ru"}}])

    def _run(self, *args) -> str:
        out = StringIO()
        with patch(
            "apps.integrations.services.lxp_graphql_client.LXPGraphQLClient.get_token", return_value="t"
        ), patch(
            "apps.integrations.services.lxp_graphql_client.LXPGraphQLClient._post", return_value=self.page
        ):
            call_command("backfill_lxp_user_ids", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        output = self._run("--dry-run")
        self.user.refresh_from_db()
        self.assertFalse(self.user.lxp_user_id)
        self.assertIn("lxp-100", output)

    def test_writes_when_empty(self):
        self._run()
        self.user.refresh_from_db()
        self.assertEqual(self.user.lxp_user_id, "lxp-100")

    def test_existing_id_not_overwritten_without_flag(self):
        get_user_model().objects.filter(pk=self.user.pk).update(lxp_user_id="lxp-old")
        self._run()
        self.user.refresh_from_db()
        self.assertEqual(self.user.lxp_user_id, "lxp-old")

        self._run("--overwrite")
        self.user.refresh_from_db()
        self.assertEqual(self.user.lxp_user_id, "lxp-100")
