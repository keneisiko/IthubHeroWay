"""Обход кеша ответов LXP.

Пустой ответ кешировался на шесть часов наравне с полезным: один неудачный
обход прятал данные группы до истечения TTL, и повторный запуск команды
возвращал ту же пустоту, не обращаясь к LXP.
"""

from __future__ import annotations

from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from apps.integrations.services.lxp_graphql_client import GraphQLResponse, LXPGraphQLClient


class CacheBypassTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = LXPGraphQLClient()

    def query_twice(self, bypass: bool):
        responses = [
            GraphQLResponse(data={"disciplinesByGroups": []}, errors=None),
            GraphQLResponse(data={"disciplinesByGroups": [{"id": "d1"}]}, errors=None),
        ]
        self.client.bypass_cache = bypass
        with mock.patch.object(LXPGraphQLClient, "_post", side_effect=responses) as post:
            first = self.client._cached_query("disc", "query", {}, "token")
            second = self.client._cached_query("disc", "query", {}, "token")
        return first, second, post.call_count

    def test_empty_answer_sticks_in_the_cache(self):
        first, second, calls = self.query_twice(bypass=False)

        self.assertEqual(first, second)
        self.assertEqual(calls, 1)

    def test_bypass_asks_lxp_again(self):
        first, second, calls = self.query_twice(bypass=True)

        self.assertEqual(first["disciplinesByGroups"], [])
        self.assertEqual(second["disciplinesByGroups"], [{"id": "d1"}])
        self.assertEqual(calls, 2)
