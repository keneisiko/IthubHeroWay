"""Связать людей из Hik со студентами по фамилии и имени.

В портале у людей личные почты (gmail, mail.ru), а в платформе — учебные из
LXP: пересечение нулевое, и сопоставление по почте не работает. Зато в каждом
проходе есть ФИО и код человека. Сопоставляем один раз по имени и запоминаем
код в карточке — дальше проходы привязываются по нему, а не по написанию имени.
"""

from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, Squad, User
from apps.integrations.models import HikEvent


def name_key(*parts: str) -> str:
    """Ключ сравнения имён: регистр, лишние пробелы и «ё» роли не играют."""
    tokens = []
    for part in parts:
        for token in str(part or "").replace("\xa0", " ").split():
            tokens.append(token.strip().lower().replace("ё", "е"))
    return " ".join(sorted(tokens))


def persons_from_events() -> dict[str, dict]:
    """Уникальные люди из проходов: ключ по имени, значение — коды."""
    persons: dict[str, dict] = {}
    for event in HikEvent.objects.exclude(raw_data={}).only("raw_data").iterator(chunk_size=500):
        raw = event.raw_data if isinstance(event.raw_data, dict) else {}
        full_name = str(raw.get("personName") or "").strip()
        if not full_name:
            continue
        key = name_key(full_name)
        entry = persons.setdefault(
            key, {"name": full_name, "person_id": "", "person_code": "", "events": 0}
        )
        entry["events"] += 1
        entry["person_id"] = entry["person_id"] or str(raw.get("personId") or "").strip()
        entry["person_code"] = entry["person_code"] or str(raw.get("personCode") or "").strip()
    return persons


class Command(BaseCommand):
    help = "Сопоставить проходы Hik со студентами по ФИО и запомнить коды"

    def add_arguments(self, parser):
        parser.add_argument("--squad", type=str, default="", help="Ограничить отрядом")
        parser.add_argument("--apply", action="store_true", help="Записать коды в карточки")

    def handle(self, *args, **options):
        squad_code = (options["squad"] or "").strip()
        students = User.objects.filter(role=Role.AGENT)
        if squad_code:
            if not Squad.objects.filter(code=squad_code).exists():
                raise CommandError(f"Отряд {squad_code!r} не найден")
            students = students.filter(squad__code=squad_code)

        students = list(students.only("id", "first_name", "last_name", "username", "hik_person_id"))
        if not students:
            raise CommandError("Студенты не найдены — сначала импорт группы")

        persons = persons_from_events()
        if not persons:
            raise CommandError("В базе нет проходов с именами — сначала pull_hik_web")

        # Однофамильцы с одинаковым именем неразличимы: такие пары не трогаем,
        # иначе чужие проходы попадут в рейтинг.
        by_key: dict[str, list[User]] = defaultdict(list)
        for student in students:
            by_key[name_key(student.last_name, student.first_name)].append(student)

        matched, ambiguous, missing = [], [], []
        for key, group in by_key.items():
            person = persons.get(key)
            if person is None:
                missing.extend(group)
                continue
            if len(group) > 1:
                ambiguous.extend(group)
                continue
            matched.append((group[0], person))

        self.stdout.write(f"Людей в проходах: {len(persons)} | студентов: {len(students)}")
        self.stdout.write(self.style.SUCCESS(f"Сопоставлено: {len(matched)}"))
        for student, person in matched[:20]:
            self.stdout.write(
                f"  {student.last_name} {student.first_name} → {person['name']} "
                f"(код {person['person_code'] or '—'}, проходов {person['events']})"
            )
        if ambiguous:
            self.stdout.write(self.style.WARNING(f"Полные тёзки, пропущены: {len(ambiguous)}"))
            for student in ambiguous[:10]:
                self.stdout.write(f"  {student.last_name} {student.first_name}")
        if missing:
            self.stdout.write(f"Без проходов: {len(missing)}")
            for student in missing[:10]:
                self.stdout.write(f"  {student.last_name} {student.first_name}")

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Пробный запуск: коды не записаны, добавьте --apply"))
            return

        with transaction.atomic():
            updated = 0
            for student, person in matched:
                fields = []
                if person["person_id"] and student.hik_person_id != person["person_id"]:
                    student.hik_person_id = person["person_id"]
                    fields.append("hik_person_id")
                if person["person_code"] and student.hik_card_code != person["person_code"]:
                    student.hik_card_code = person["person_code"]
                    fields.append("hik_card_code")
                if fields:
                    student.save(update_fields=fields)
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Записано кодов: {updated}. Теперь повторите обработку проходов: "
                "manage.py sync_hik_events"
            )
        )
