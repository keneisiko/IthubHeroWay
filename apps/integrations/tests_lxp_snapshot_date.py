"""Подпись ночного снимка LXP — вчерашняя дата по Москве.

Задача идёт в 02:00 по Москве (23:00 UTC предыдущего дня). Дата бралась
из UTC, и снимок подписывался позавчерашним числом: «15.10» создан 17.10.
"""

from __future__ import annotations

from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import TestCase

from apps.integrations import tasks

NIGHT_RUN = datetime(2026, 10, 22, 2, 0, tzinfo=ZoneInfo("Europe/Moscow"))


class SnapshotDateTests(TestCase):
    def test_night_run_labels_yesterday_not_the_day_before(self):
        client = mock.Mock()
        client.fetch_all_data.return_value = {}
        with (
            mock.patch("django.utils.timezone.now", return_value=NIGHT_RUN),
            mock.patch.object(tasks, "LXPGraphQLClient", return_value=client),
            mock.patch.object(tasks, "save_snapshot", return_value=(None, False)) as save,
        ):
            tasks.fetch_lxp_snapshot()

        self.assertEqual(save.call_args.args[0].isoformat(), "2026-10-21")
