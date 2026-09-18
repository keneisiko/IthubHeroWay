"""Поиск полей в схеме LXP по ключевому слову.

Квесты на опоздания считались только по HikCentral, а он недоступен. Из
снимка LXP приходит агрегат `visited/total/percent` — по нему видно, был ли
студент на занятии, но не видно, пришёл ли вовремя. Есть ли в схеме поштучные
отметки посещения, из документации неизвестно: спрашиваем саму схему.
"""

from __future__ import annotations

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
            response = client._post(INTROSPECTION_QUERY, {}, token=token, timeout=60)
        except (LXPAuthError, LXPRequestError) as e:
            raise CommandError(f"LXP: {e}") from e
        if response.errors:
            raise CommandError(f"LXP отклонил интроспекцию: {response.errors}")

        types = ((response.data or {}).get("__schema") or {}).get("types") or []
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
