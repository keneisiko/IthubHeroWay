"""Оставить в базе только один отряд.

Закрытый прогон идёт на одной группе, а в базе лежит весь колледж: чужие
карточки мешают и в отчётах, и в поиске соперников. Команда удаляет
остальных агентов вместе с их журналами (каскадом), не трогая сотрудников —
без администратора и куратора в платформу потом не войти.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, Squad, User


class Command(BaseCommand):
    help = "Удалить всех агентов, кроме состава указанного отряда"

    def add_arguments(self, parser):
        parser.add_argument("squad_code", type=str, help="Код отряда, который остаётся")
        parser.add_argument("--dry-run", action="store_true", help="Показать, кого удалит, ничего не удаляя")
        parser.add_argument(
            "--drop-empty-squads",
            action="store_true",
            help="Заодно удалить отряды, в которых после чистки никого не осталось",
        )

    def handle(self, *args, **options):
        code = options["squad_code"].strip()
        squad = Squad.objects.filter(code=code).first()
        if squad is None:
            available = ", ".join(Squad.objects.values_list("code", flat=True)) or "нет ни одного"
            raise CommandError(f"Отряд {code!r} не найден. Доступные: {available}")

        keep = User.objects.filter(squad=squad)
        if not keep.exists():
            raise CommandError(f"В отряде {squad.code} никого нет — чистить по нему нечего")

        # Сотрудники и суперпользователи остаются в любом случае: иначе после
        # чистки в админку некому зайти и некому подтверждать заявки.
        doomed = (
            User.objects.filter(role=Role.AGENT)
            .exclude(squad=squad)
            .exclude(is_staff=True)
            .exclude(is_superuser=True)
        )

        total = doomed.count()
        self.stdout.write(f"Останется: отряд {squad.code} «{squad.name}» — {keep.count()} человек")
        self.stdout.write(f"Под удаление: {total} агентов")
        for user in doomed.order_by("username")[:10]:
            self.stdout.write(f"  {user.username}  {user.email}")
        if total > 10:
            self.stdout.write(f"  … и ещё {total - 10}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Пробный запуск: ничего не удалено"))
            return

        with transaction.atomic():
            deleted, _ = doomed.delete()
            dropped = 0
            if options["drop_empty_squads"]:
                empty = Squad.objects.exclude(code=squad.code).filter(members__isnull=True)
                dropped = empty.count()
                empty.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Удалено записей: {deleted} (агентов {total}), отрядов удалено: {dropped}. "
                f"Остался отряд {squad.code}."
            )
        )
