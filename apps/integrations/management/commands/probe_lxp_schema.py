"""Поиск полей в схеме LXP по ключевому слову.

Квесты на опоздания считались только по HikCentral, а он недоступен. Из
снимка LXP приходит агрегат `visited/total/percent` — по нему видно, был ли
студент на занятии, но не видно, пришёл ли вовремя. Есть ли в схеме поштучные
отметки посещения, из документации неизвестно: спрашиваем саму схему.
"""

from __future__ import annotations

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.integrations.services.lxp_graphql_client import (
    LXPAuthError,
    LXPGraphQLClient,
    LXPRequestError,
)

INTROSPECTION_QUERY = """
query ProbeSchema {
  __schema {
    types {
      name
      kind
      fields { name type { name kind ofType { name kind } } }
    }
  }
}
"""

DEFAULT_WORDS = ["attend", "visit", "late", "lesson", "schedule", "absence", "presen"]


class Command(BaseCommand):
    help = "Показать типы и поля схемы LXP, подходящие под ключевые слова"

    def add_arguments(self, parser):
        parser.add_argument(
            "--word",
            action="append",
            default=[],
            dest="words",
            help=f"Ключевое слово (можно повторять). По умолчанию: {', '.join(DEFAULT_WORDS)}",
        )
        parser.add_argument("--type", type=str, default="", help="Показать все поля одного типа целиком")

    def handle(self, *args, **options):
        client = LXPGraphQLClient()
        try:
            token = client.get_token()
        except (LXPAuthError, LXPRequestError) as e:
            raise CommandError(f"LXP: {e}") from e

        # Запрос идёт мимо клиента намеренно: тот прячет тела ответов, потому
        # что в них попадают токены. Здесь ответ — это сама схема или отказ
        # интроспекции, секретов в нём нет, а причина отказа нужна целиком.
        try:
            raw = requests.post(
                settings.LXP_GRAPHQL_ENDPOINT,
                json={"query": INTROSPECTION_QUERY, "variables": {}},
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                timeout=60,
            )
        except requests.RequestException as e:
            raise CommandError(f"LXP недоступен: {type(e).__name__}") from e

        if raw.status_code >= 400:
            self.stdout.write(self.style.WARNING(f"HTTP {raw.status_code}. Ответ сервера:"))
            self.stdout.write(raw.text[:1500])
            raise CommandError(
                "Интроспекция отклонена. Обычно это значит, что она закрыта на боевом LXP — "
                "тогда список полей по посещаемости придётся спросить у команды LXP."
            )

        payload = raw.json()
        if payload.get("errors"):
            self.stdout.write(self.style.WARNING("GraphQL вернул ошибки:"))
            self.stdout.write(str(payload["errors"])[:1500])
            raise CommandError("Интроспекция отклонена сервером LXP")

        types = ((payload.get("data") or {}).get("__schema") or {}).get("types") or []
        if not types:
            raise CommandError("Схема пришла пустой: интроспекция, возможно, закрыта на сервере LXP")

        wanted_type = (options["type"] or "").strip().lower()
        if wanted_type:
            for entry in types:
                if (entry.get("name") or "").lower() == wanted_type:
                    self._print_type(entry, full=True)
                    return
            raise CommandError(f"Тип {options['type']!r} в схеме не найден")

        words = [w.lower() for w in (options["words"] or DEFAULT_WORDS)]
        found = 0
        for entry in types:
            name = entry.get("name") or ""
            if name.startswith("__"):
                continue
            hit_type = any(w in name.lower() for w in words)
            hits = [
                f.get("name")
                for f in (entry.get("fields") or [])
                if any(w in (f.get("name") or "").lower() for w in words)
            ]
            if hit_type or hits:
                found += 1
                self.stdout.write(self.style.NOTICE(f"{entry.get('kind')} {name}"))
                for field in (entry.get("fields") or []) if hit_type else []:
                    self.stdout.write(f"    {field.get('name')}")
                for field_name in hits if not hit_type else []:
                    self.stdout.write(f"    {field_name}")
        self.stdout.write(self.style.SUCCESS(f"Совпадений: {found}. Слова: {', '.join(words)}"))

    def _print_type(self, entry: dict, full: bool = False):
        self.stdout.write(self.style.NOTICE(f"{entry.get('kind')} {entry.get('name')}"))
        for field in entry.get("fields") or []:
            type_info = field.get("type") or {}
            type_name = type_info.get("name") or (type_info.get("ofType") or {}).get("name") or type_info.get("kind")
            self.stdout.write(f"    {field.get('name')}: {type_name}")
