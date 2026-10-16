"""Импорт одной учебной группы LXP в отряд.

`import_lxp_students` тянет весь колледж без деления на группы: для пилота
на одной группе из такого списка отряд не собрать. Здесь наоборот — сначала
выбирается группа, затем её состав попадает в отряд.

Весь колледж сразу заводит `import_lxp_all_groups`; сам импорт у обеих
команд один и тот же — `apps.integrations.services.lxp_group_import`.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.integrations.services.lxp_graphql_client import LXPAuthError, LXPRequestError
from apps.integrations.services.lxp_group_import import course_from_name, import_group, slug
from apps.integrations.services.lxp_groups import group_students, list_groups


class Command(BaseCommand):
    help = "Импортировать состав учебной группы LXP в отряд платформы"

    def add_arguments(self, parser):
        parser.add_argument("--list", action="store_true", help="Показать доступные группы и выйти")
        parser.add_argument("--group-id", type=str, default="", help="ID группы из --list")
        parser.add_argument("--squad-code", type=str, default="", help="Код отряда (латиницей)")
        parser.add_argument(
            "--squad-name", type=str, default="", help="Название отряда; по умолчанию — имя группы"
        )
        parser.add_argument(
            "--course",
            type=int,
            default=0,
            help="Курс отряда; по умолчанию берётся из первой цифры названия группы",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Показать, что произойдёт, ничего не записывая"
        )

    def handle(self, *args, **options):
        try:
            if options["list"]:
                self._print_groups()
                return
            self._import(options)
        except (LXPAuthError, LXPRequestError) as e:
            raise CommandError(f"LXP: {e}") from e

    def _print_groups(self):
        groups = list_groups()
        if not groups:
            self.stdout.write(
                self.style.WARNING("Групп не нашлось: у бот-аккаунта нет подорганизаций")
            )
            return
        for group in groups:
            suffix = f"  ({group['suborganization']})" if group["suborganization"] else ""
            course = course_from_name(group["name"]) or "?"
            self.stdout.write(f"{group['id']}  курс {course}  {group['name']}{suffix}")
        self.stdout.write(self.style.NOTICE(f"Всего групп: {len(groups)}"))

    def _group_name(self, group_id: str) -> str:
        for group in list_groups():
            if str(group.get("id")) == group_id:
                return group.get("name") or ""
        return ""

    def _import(self, options):
        group_id = (options["group_id"] or "").strip()
        if not group_id:
            raise CommandError("Укажите --group-id (список групп: --list)")

        lxp_name = self._group_name(group_id)
        squad_name = (options["squad_name"] or "").strip() or lxp_name or f"Группа {group_id}"

        course = int(options["course"] or 0) or course_from_name(lxp_name)
        if not 1 <= course <= 4:
            raise CommandError(
                "Курс не читается из названия группы — укажите --course от 1 до 4"
            )

        students = group_students(group_id)
        if not students:
            raise CommandError(f"В группе {group_id} нет действующих студентов")

        squad_code = slug(
            options["squad_code"] or lxp_name or f"lxp-{group_id}", fallback=f"lxp-{group_id}"[:50]
        )

        if options["dry_run"]:
            self.stdout.write(
                f"Отряд {squad_code} «{squad_name}», курс {course}: {len(students)} студентов"
            )
            for item in students[:200]:
                user = item.get("user") or {}
                name = (
                    " ".join(filter(None, [user.get("lastName"), user.get("firstName")]))
                    or user.get("id")
                )
                self.stdout.write(f"  {name}  {user.get('email') or ''}")
            return

        result = import_group(
            group_id=group_id,
            squad_code=squad_code,
            squad_name=squad_name,
            course=course,
            students=students,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Отряд {result.squad_code} «{result.squad_name}», курс {result.course}: "
                f"{result.students} студентов (новых карточек {result.created}, "
                f"уже были {result.matched}). "
                "Вход открывается после привязки Telegram."
            )
        )
