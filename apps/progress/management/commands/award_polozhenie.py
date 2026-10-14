"""Разовые начисления по разделам 5-7 Положения и списания по разделу 9.

    python manage.py award_polozhenie --tariffs
    python manage.py award_polozhenie event --user ivanov --key hack-2026-10 \\
        --level region --role speaker --title "Хакатон КБР"
    python manage.py award_polozhenie olympiad --user ivanov --key olymp-prog-2026 \\
        --level federal --role win
    python manage.py award_polozhenie project --user ivanov --key inc-42-stage-1 \\
        --role stage --title "Этап 1: прототип"
    python manage.py award_polozhenie absence --user ivanov --day 2026-10-20

Начисления идемпотентны: повторный запуск с тем же ключом ничего не удвоит.
Списание применяется только после подтверждения причины тьютором (п. 9.2).
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.progress.services.polozhenie_awards import (
    UnknownTariff,
    absence_penalty_for_day,
    award_event,
    award_olympiad,
    award_project,
)

KINDS = ("event", "olympiad", "project", "absence")


class Command(BaseCommand):
    help = "Начисление за мероприятие, олимпиаду, проект или списание за пропуски."

    def add_arguments(self, parser):
        parser.add_argument("kind", nargs="?", choices=KINDS, help="Что начисляем.")
        parser.add_argument("--user", type=str, default="", help="Логин, email или позывной студента.")
        parser.add_argument("--key", type=str, default="", help="Ключ активности: по нему не платим дважды.")
        parser.add_argument("--level", type=str, default="", help="Уровень: college/city/region/federal.")
        parser.add_argument("--role", type=str, default="", help="Роль, результат или вид работы.")
        parser.add_argument("--title", type=str, default="", help="Название для истории студента.")
        parser.add_argument("--day", type=str, default="", help="Дата события (ГГГГ-ММ-ДД).")
        parser.add_argument("--note", type=str, default="", help="Примечание в журнал.")
        parser.add_argument("--by", type=str, default="", help="Логин сотрудника, подтвердившего начисление.")
        parser.add_argument("--tariffs", action="store_true", help="Показать тарифы и выйти.")

    def handle(self, *args, **options):
        if options["tariffs"]:
            self._print_tariffs()
            return

        kind = options["kind"]
        if not kind:
            raise CommandError("Укажите вид начисления или --tariffs.")

        user = self._find_user(options["user"])
        confirmed_by = self._find_user(options["by"]) if options["by"] else None
        happened_on = self._parse_day(options["day"])

        try:
            outcome = self._dispatch(kind, user, confirmed_by, happened_on, options)
        except UnknownTariff as exc:
            raise CommandError(str(exc)) from exc

        if not outcome.granted:
            self.stdout.write(
                self.style.WARNING(f"Ничего не начислено ({outcome.note or 'уже начислено'}).")
            )
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"{user.username}: рейтинг {outcome.rating:+}, монеты {outcome.coins:+}"
            )
        )

    def _dispatch(self, kind, user, confirmed_by, happened_on, options):
        if kind == "absence":
            return absence_penalty_for_day(
                user, happened_on or date.today(), confirmed_by=confirmed_by, note=options["note"]
            )

        key = options["key"].strip()
        if not key:
            raise CommandError("--key обязателен: по нему Положение запрещает платить дважды.")
        role = options["role"].strip()
        if not role:
            raise CommandError("--role обязателен.")

        if kind == "project":
            return award_project(
                user,
                activity_key=key,
                result=role,
                title=options["title"],
                happened_on=happened_on,
                confirmed_by=confirmed_by,
                note=options["note"],
            )

        level = options["level"].strip()
        if not level:
            raise CommandError("--level обязателен.")

        if kind == "event":
            return award_event(
                user,
                activity_key=key,
                level=level,
                role=role,
                title=options["title"],
                happened_on=happened_on,
                confirmed_by=confirmed_by,
                note=options["note"],
            )
        return award_olympiad(
            user,
            activity_key=key,
            level=level,
            result=role,
            title=options["title"],
            happened_on=happened_on,
            confirmed_by=confirmed_by,
            note=options["note"],
        )

    def _parse_day(self, raw: str) -> date | None:
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise CommandError(f"Неверная дата: {raw}") from exc

    def _find_user(self, raw: str):
        raw = (raw or "").strip()
        if not raw:
            raise CommandError("--user обязателен.")
        User = get_user_model()
        for field in ("username", "email", "callsign"):
            found = User.objects.filter(**{f"{field}__iexact": raw}).first()
            if found:
                return found
        raise CommandError(f"Студент не найден: {raw}")

    def _print_tariffs(self) -> None:
        from django.conf import settings

        self.stdout.write(self.style.MIGRATE_HEADING("Мероприятия (раздел 5), рейтинг / монеты"))
        self._matrix(
            settings.POLOZHENIE_EVENT_ROLES,
            settings.POLOZHENIE_EVENT_LEVELS,
            settings.POLOZHENIE_EVENT_TARIFFS,
            settings.POLOZHENIE_EVENT_ROLE_TITLES,
            settings.POLOZHENIE_EVENT_LEVEL_TITLES,
        )
        self.stdout.write(self.style.MIGRATE_HEADING("\nОлимпиады (раздел 6), рейтинг / монеты"))
        self._matrix(
            settings.POLOZHENIE_OLYMPIAD_RESULTS,
            settings.POLOZHENIE_OLYMPIAD_LEVELS,
            settings.POLOZHENIE_OLYMPIAD_TARIFFS,
            settings.POLOZHENIE_OLYMPIAD_RESULT_TITLES,
            settings.POLOZHENIE_OLYMPIAD_LEVEL_TITLES,
        )
        self.stdout.write(self.style.MIGRATE_HEADING("\nПроекты (раздел 7)"))
        for code, row in settings.POLOZHENIE_PROJECT_TARIFFS.items():
            self.stdout.write(f"  {code:<10}{row['title']:<36}{row['rating']} / {row['coins']}")
        self.stdout.write(self.style.MIGRATE_HEADING("\nРоли (раздел 4), за полную неделю"))
        for code, row in settings.POLOZHENIE_ROLES.items():
            self.stdout.write(f"  {code:<16}{row['title']:<38}{row['rating']} / {row['coins']}")
        self.stdout.write(self.style.MIGRATE_HEADING("\nСписания (раздел 9)"))
        penalties = settings.POLOZHENIE_PENALTIES
        self.stdout.write(
            f"  {penalties['ABSENCE_PER_LESSON']} за пропущенную пару, "
            f"не больше {penalties['ABSENCE_DAILY_MAX']} за учебный день; монеты не списываются"
        )

    def _matrix(self, rows, levels, tariffs, row_titles, level_titles) -> None:
        header = " " * 42 + "".join(f"{level_titles[lv]:>14}" for lv in levels)
        self.stdout.write(header)
        for row in rows:
            line = f"  {row_titles[row]:<40}"
            for level in levels:
                rating, coins = tariffs[(row, level)]
                line += f"{f'{rating} / {coins}':>14}"
            self.stdout.write(line)
