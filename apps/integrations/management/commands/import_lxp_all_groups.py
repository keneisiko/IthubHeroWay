"""Завести весь колледж: каждая группа LXP — отряд платформы.

`import_lxp_students` тянет студентов списком, без деления на группы, а
`import_lxp_group` берёт одну группу за вызов и требует придумать код,
название и курс руками. Для трёх десятков групп это тридцать вызовов,
в каждом можно опечататься.

Здесь код отряда получается транслитерацией названия группы, а курс — из
первой цифры названия («3ИТР2.9.24» — третий курс). Группы, у которых курс
по названию не читается, пропускаются: поставить его наугад значит
разойтись с реальностью в отчётах по курсам.

    python manage.py import_lxp_all_groups --dry-run
    python manage.py import_lxp_all_groups
    python manage.py import_lxp_all_groups --course 3
    python manage.py import_lxp_all_groups --only 3ИТР2.9.24
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.integrations.services.lxp_graphql_client import LXPAuthError, LXPRequestError
from apps.integrations.services.lxp_group_import import (
    course_from_name,
    import_group,
    squad_code_for,
)
from apps.integrations.services.lxp_groups import group_students, list_groups


class Command(BaseCommand):
    help = "Импортирует все учебные группы LXP в отряды платформы."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Показать план, ничего не записывая.")
        parser.add_argument("--course", type=int, default=0, help="Только группы этого курса.")
        parser.add_argument(
            "--only",
            type=str,
            default="",
            help="Только группы, в названии которых есть эта подстрока.",
        )
        parser.add_argument(
            "--default-course",
            type=int,
            default=0,
            help="Какой курс ставить группам, где он не читается из названия (по умолчанию пропускать).",
        )

    def handle(self, *args, **options):
        try:
            groups = list_groups()
        except (LXPAuthError, LXPRequestError) as exc:
            raise CommandError(f"LXP: {exc}") from exc

        if not groups:
            raise CommandError("Групп не нашлось: у бот-аккаунта нет подорганизаций.")

        selected, skipped = self._select(groups, options)

        if not selected:
            raise CommandError("Под условия отбора не подошла ни одна группа.")

        if options["dry_run"]:
            self._preview(selected, skipped)
            return

        self._import(selected, skipped)

    def _select(self, groups: list[dict], options: dict) -> tuple[list[tuple[dict, int]], list[dict]]:
        needle = (options["only"] or "").strip().lower()
        wanted_course = int(options["course"] or 0)
        default_course = int(options["default_course"] or 0)

        selected: list[tuple[dict, int]] = []
        skipped: list[dict] = []
        for group in groups:
            name = group.get("name") or ""
            if needle and needle not in name.lower():
                continue
            course = course_from_name(name) or default_course
            if not 1 <= course <= 4:
                skipped.append(group)
                continue
            if wanted_course and course != wanted_course:
                continue
            selected.append((group, course))
        return selected, skipped

    def _preview(self, selected: list[tuple[dict, int]], skipped: list[dict]) -> None:
        self.stdout.write(f"{'Код отряда':<28}{'Курс':>5}  Группа")
        for group, course in selected:
            self.stdout.write(f"{squad_code_for(group):<28}{course:>5}  {group.get('name')}")
        self.stdout.write(self.style.NOTICE(f"\nБудет заведено отрядов: {len(selected)}"))
        self._report_skipped(skipped)
        self.stdout.write(
            "Состав групп не запрашивался: это план по названиям. "
            "Запустите без --dry-run, чтобы импортировать студентов."
        )

    def _import(self, selected: list[tuple[dict, int]], skipped: list[dict]) -> None:
        total_students = total_created = total_matched = 0
        failed: list[tuple[str, str]] = []

        self.stdout.write(f"{'Код отряда':<28}{'Курс':>5}{'Всего':>7}{'Новых':>7}  Группа")
        for group, course in selected:
            name = group.get("name") or ""
            group_id = str(group.get("id") or "")
            try:
                students = group_students(group_id)
            except (LXPAuthError, LXPRequestError) as exc:
                # Одна недоступная группа не должна отменять весь импорт:
                # отчёт в конце покажет, какие остались незаведёнными.
                failed.append((name, str(exc)))
                continue

            if not students:
                failed.append((name, "нет действующих студентов"))
                continue

            result = import_group(
                group_id=group_id,
                squad_code=squad_code_for(group),
                squad_name=name,
                course=course,
                students=students,
            )
            total_students += result.students
            total_created += result.created
            total_matched += result.matched
            self.stdout.write(
                f"{result.squad_code:<28}{result.course:>5}{result.students:>7}"
                f"{result.created:>7}  {result.squad_name}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nОтрядов заведено: {len(selected) - len(failed)}. "
                f"Студентов: {total_students} (новых карточек {total_created}, "
                f"уже были {total_matched})."
            )
        )
        self.stdout.write(
            "Карточки закрыты для входа: он открывается после /activate в Telegram-боте."
        )
        if failed:
            self.stdout.write(self.style.ERROR(f"\nНе удалось завести ({len(failed)}):"))
            for name, reason in failed:
                self.stdout.write(f"  {name}: {reason}")
        self._report_skipped(skipped)
        self.stdout.write(
            "\nДальше: загрузить расписание и отметки посещения — они идут по "
            "lxp_group_id, который теперь есть у каждого отряда."
        )

    def _report_skipped(self, skipped: list[dict]) -> None:
        if not skipped:
            return
        self.stdout.write(
            self.style.WARNING(f"\nКурс не читается из названия, пропущено ({len(skipped)}):")
        )
        for group in skipped:
            self.stdout.write(f"  {group.get('name')}  ({group.get('id')})")
        self.stdout.write(
            "Заведите их по одной через import_lxp_group --course, "
            "либо задайте --default-course."
        )
