"""Перебор имён полей в закрытой схеме LXP.

Интроспекция на боевом LXP выключена Apollo, поэтому список полей не получить.
Но на неизвестное поле Apollo отвечает «Cannot query field X ... Did you mean
Y?» — по этим подсказкам видно, как поля называются на самом деле. Нужно это
ради опозданий: из снимка приходит только агрегат visited/total/percent,
по которому нельзя отличить пришедшего вовремя от опоздавшего.
"""

from __future__ import annotations

import re

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.integrations.services.lxp_graphql_client import (
    LXPAuthError,
    LXPGraphQLClient,
    LXPRequestError,
)

# Поля проверяются внутри studentDiscipline: это единственное место, где мы
# уже видим посещаемость, и логично ожидать там же поштучные отметки.
CANDIDATES = [
    "attendance",
    "attendances",
    "lessonAttendance",
    "lessonsAttendance",
    "studentAttendance",
    "visits",
    "lessonVisits",
    "lessons",
    "schedule",
    "absences",
    "disciplineAttendanceDetails",
    "disciplineAttendanceByLesson",
]

SUGGESTION = re.compile(r"Did you mean ([^?]+)\?")


class Command(BaseCommand):
    help = "Проверить, существуют ли поля в схеме LXP (интроспекция закрыта)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--field", action="append", default=[], dest="fields", help="Имя поля (можно повторять)"
        )
        parser.add_argument(
            "--container",
            action="append",
            default=[],
            dest="containers",
            help=(
                "Уровень вложенности (можно повторять — вложение по порядку). "
                "Без аргумента проверяются поля корневого Query."
            ),
        )
        parser.add_argument(
            "--in-discipline",
            action="store_true",
            help="Проверять внутри studentDiscipline — там, где сейчас приходит посещаемость",
        )

    def handle(self, *args, **options):
        try:
            token = LXPGraphQLClient().get_token()
        except (LXPAuthError, LXPRequestError) as e:
            raise CommandError(f"LXP: {e}") from e

        fields = options["fields"] or CANDIDATES
        containers = list(options["containers"])
        if options["in_discipline"] and not containers:
            # studentDiscipline не поле корневого Query: он лежит внутри
            # состава группы, и проверять его имена нужно там же.
            containers = [
                'searchStudentsInLearningGroup(input: {filters: '
                '{learningGroupId: "00000000-0000-0000-0000-000000000000", isExpelled: false}})',
                "items",
                'studentDiscipline(disciplineId: "00000000-0000-0000-0000-000000000000")',
            ]
        where = " → ".join(c.split("(")[0] for c in containers) or "Query (корень)"
        self.stdout.write(self.style.NOTICE(f"Ищем поля в: {where}"))
        found, suggestions = [], {}

        for field in fields:
            query = self._build_query(containers, field)
            status, errors = self._ask(query, token)
            if status == "ok":
                found.append(field)
                self.stdout.write(self.style.SUCCESS(f"  есть: {field}"))
                continue
            if status == "leaf":
                # Поле существует, но скалярное — подзапрос ему не нужен.
                found.append(field)
                self.stdout.write(self.style.SUCCESS(f"  есть (скаляр): {field}"))
                continue
            hint = SUGGESTION.search(errors)
            if hint:
                names = [n.strip().strip('"') for n in re.split(r"[,]| or ", hint.group(1)) if n.strip()]
                suggestions[field] = names
                self.stdout.write(f"  нет: {field} → похоже на: {', '.join(names)}")
            else:
                self.stdout.write(f"  нет: {field}")

        self.stdout.write("")
        if found:
            self.stdout.write(self.style.SUCCESS(f"Найденные поля: {', '.join(found)}"))
        else:
            self.stdout.write(self.style.WARNING("Ни одно из имён не подошло"))
        all_hints = sorted({n for names in suggestions.values() for n in names})
        if all_hints:
            self.stdout.write(f"Подсказки схемы: {', '.join(all_hints)}")
            self.stdout.write("Проверить их: --field " + " --field ".join(all_hints[:10]))

    @staticmethod
    def _build_query(containers: list[str], field: str) -> str:
        body = f"{field} {{ __typename }}"
        for container in reversed(containers):
            body = f"{container} {{ {body} }}"
        return f"query Probe {{ {body} }}"

    def _ask(self, query: str, token: str) -> tuple[str, str]:
        try:
            raw = requests.post(
                settings.LXP_GRAPHQL_ENDPOINT,
                json={"query": query, "variables": {}},
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                timeout=40,
            )
        except requests.RequestException as e:
            raise CommandError(f"LXP недоступен: {type(e).__name__}") from e

        try:
            payload = raw.json()
        except ValueError:
            return "error", raw.text[:300]

        errors = payload.get("errors") or []
        text = " ".join(str(e.get("message") or "") for e in errors if isinstance(e, dict))
        if not errors:
            return "ok", ""
        # «Field must not have a selection since type has no subfields» —
        # поле есть, просто оно скалярное.
        if "must not have a selection" in text or "no subfields" in text:
            return "leaf", text
        if "Cannot query field" in text:
            return "missing", text
        # Ошибка выполнения (например, несуществующий id) означает, что
        # валидацию запрос прошёл, то есть поле существует.
        if "Cannot query" not in text and "Unknown argument" not in text:
            return "ok", text
        return "missing", text
