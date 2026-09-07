"""Снимок LXP по одной группе.

Обход всего колледжа — 48 групп с дисциплинами по каждой — занимал около
четверти часа, тогда как закрытый прогон идёт на одной группе.
"""

from __future__ import annotations

from datetime import date
from unittest import mock

from django.test import TestCase

from apps.integrations.services.lxp_graphql_client import LXPGraphQLClient

ME = {
    "getMe": {
        "assignedSuborganizations": [
            {"suborganizationId": "sub1", "suborganization": {"id": "sub1", "organizationId": "org1"}}
        ]
    }
}
GROUPS = {"getLearningGroups": [{"id": "g-ours", "name": "3ИТР2"}, {"id": "g-other", "name": "1Д1"}]}


class SnapshotGroupFilterTests(TestCase):
    def setUp(self):
        self.client = LXPGraphQLClient()
        self.visited: list[str] = []

    def fake_query(self, name, query, variables, token, **kwargs):
        if "get_me" in name:
            return {"ok": True, "data": ME}
        if "_lg_" in name:
            return {"ok": True, "data": GROUPS}
        if "_disc_" in name:
            self.visited.append(str((variables.get("input") or {}).get("groupIds")))
            return {"ok": True, "data": {"disciplinesByGroups": []}}
        return {"ok": True, "data": {}}

    def run_walk(self, only):
        with mock.patch.object(LXPGraphQLClient, "_safe_cached_query", side_effect=self.fake_query):
            return self.client._fetch_learning_groups_performance(
                "token", cache_prefix=date(2026, 9, 7).isoformat(), only_group_ids=only
            )

    def test_only_the_named_group_is_walked(self):
        self.run_walk({"g-ours"})

        self.assertEqual(self.visited, ["['g-ours']"])

    def test_without_a_filter_every_group_is_walked(self):
        self.run_walk(None)

        self.assertEqual(self.visited, ["['g-ours']", "['g-other']"])

    def test_filtered_walk_counts_only_what_it_processed(self):
        result = self.run_walk({"g-ours"})

        self.assertEqual(result["groups_processed"], 1)
