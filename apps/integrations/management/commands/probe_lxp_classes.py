"""Занятия LXP и отметки посещения: реальные значения.

Перебор имён показал, что у занятия (`searchClasses.items`) есть время `from`,
дисциплина и отметки `attendance { studentId status }`. Каких значений бывает
`status` — из закрытой схемы не узнать, а от этого зависит, можно ли считать
опоздания без HikCentral. Спрашиваем сами данные.
"""

from __future__ import annotations

from collections import Counter

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.integrations.services.lxp_graphql_client import (
    LXPAuthError,
    LXPGraphQLClient,
    LXPRequestError,
)


def build_query(time_fields: str) -> str:
    return f"""
query ProbeClasses {{
  searchClasses {{
    total
    items {{
      id
      {time_fields}
      discipline {{ name }}
      attendance {{ studentId status }}
    }}
  }}
}}
"""


class Command(BaseCommand):
    help = "Показать занятия LXP и встречающиеся статусы посещения"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=5, help="Сколько занятий распечатать")
        parser.add_argument(
            "--time-fields",
            type=str,
            default="from to",
            help="Поля времени занятия через пробел; пусто — не запрашивать",
        )

    def handle(self, *args, **options):
        try:
            token = LXPGraphQLClient().get_token()
        except (LXPAuthError, LXPRequestError) as e:
            raise CommandError(f"LXP: {e}") from e

        time_fields = " ".join((options["time_fields"] or "").split())
        payload = self._ask(build_query(time_fields), token)
        errors = payload.get("errors")
        if errors:
            self.stdout.write(self.style.WARNING("LXP вернул ошибки:"))
            self.stdout.write(str(errors)[:1200])
            raise CommandError(
                "Запрос отклонён. Если ругается на поля времени, повторите с "
                "--time-fields '' и подберите имена через probe_lxp_fields."
            )

        root = (payload.get("data") or {}).get("searchClasses") or {}
        items = root.get("items") or []
        self.stdout.write(f"Занятий доступно: {root.get('total')}, получено: {len(items)}")
        if not items:
            self.stdout.write(self.style.WARNING("Список пуст: у бот-аккаунта нет доступа к занятиям"))
            return

        statuses: Counter[str] = Counter()
        for item in items:
            for mark in item.get("attendance") or []:
                statuses[str(mark.get("status"))] += 1

        for item in items[: int(options["limit"])]:
            discipline = (item.get("discipline") or {}).get("name") or "—"
            when = " ".join(str(item.get(f) or "") for f in time_fields.split()) or "без времени"
            marks = item.get("attendance") or []
            self.stdout.write(f"\n{discipline} | {when} | отметок: {len(marks)}")
            for mark in marks[:5]:
                self.stdout.write(f"    {mark.get('studentId')} → {mark.get('status')}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Встреченные статусы посещения:"))
        for status, count in statuses.most_common():
            self.stdout.write(f"  {status}: {count}")
        self.stdout.write(
            "\nЕсли среди статусов есть отдельный «опоздал» — квест на опоздания "
            "можно считать по LXP, без HikCentral."
        )

    def _ask(self, query: str, token: str) -> dict:
        try:
            raw = requests.post(
                settings.LXP_GRAPHQL_ENDPOINT,
                json={"query": query, "variables": {}},
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                timeout=60,
            )
        except requests.RequestException as e:
            raise CommandError(f"LXP недоступен: {type(e).__name__}") from e
        try:
            return raw.json()
        except ValueError as e:
            raise CommandError(f"LXP вернул не JSON: HTTP {raw.status_code}") from e
