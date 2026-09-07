"""Что платформа насчитала отряду.

Закрытый прогон идёт без входа студентов: проверять результат некому и негде,
кроме как в базе. Команда показывает срез по отряду — рейтинг, из чего он
сложился, кто остался с нулём и по какой причине.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q, Sum

from apps.accounts.models import Role, Squad, User
from apps.progress.models import RatingChangeSource, RatingLog
from apps.quests.models import UserQuestProgress

SOURCE_LABELS = dict(RatingChangeSource.choices)


class Command(BaseCommand):
    help = "Отчёт по отряду: рейтинг, источники начислений, кто без движения"

    def add_arguments(self, parser):
        parser.add_argument("squad_code", type=str, help="Код отряда, например pi-31")
        parser.add_argument("--limit", type=int, default=0, help="Показать только N студентов (0 = всех)")

    def handle(self, *args, **options):
        code = options["squad_code"].strip()
        squad = Squad.objects.filter(code=code).first()
        if squad is None:
            available = ", ".join(Squad.objects.values_list("code", flat=True)) or "нет ни одного"
            raise CommandError(f"Отряд {code!r} не найден. Доступные: {available}")

        members = list(
            # Куратор и админ числятся в отряде, но соревнуются не они.
            User.objects.filter(squad=squad, role=Role.AGENT)
            .annotate(
                quests_done=Count(
                    "quest_progress", filter=Q(quest_progress__is_completed=True), distinct=True
                ),
            )
            .order_by("-rating_current", "last_name")
        )
        if not members:
            raise CommandError(f"В отряде {squad.code} нет студентов — сначала импорт группы")

        self.stdout.write(f"Отряд {squad.code} «{squad.name}», курс {squad.course}: {len(members)} студентов")

        ratings = [m.rating_current for m in members]
        idle = [m for m in members if not RatingLog.objects.filter(user=m).exclude(delta=0).exists()]
        self.stdout.write(
            f"Рейтинг: минимум {min(ratings)}, медиана {sorted(ratings)[len(ratings) // 2]}, "
            f"максимум {max(ratings)}, разброс {max(ratings) - min(ratings)}"
        )
        self.stdout.write(f"Без единого начисления: {len(idle)} из {len(members)}")

        by_source = (
            RatingLog.objects.filter(user__squad=squad)
            .exclude(delta=0)
            .values("source")
            .annotate(total=Sum("delta"), n=Count("id"))
            .order_by("-total")
        )
        self.stdout.write("Источники начислений по отряду:")
        if not by_source:
            self.stdout.write("  пусто — данные ещё не подтягивались")
        for row in by_source:
            label = SOURCE_LABELS.get(row["source"], row["source"])
            self.stdout.write(f"  {label}: {row['total']:+d} за {row['n']} записей")

        limit = int(options["limit"] or 0)
        shown = members[:limit] if limit else members
        self.stdout.write("Студенты:")
        for member in shown:
            name = " ".join(filter(None, [member.last_name, member.first_name])) or member.username
            pending = UserQuestProgress.objects.filter(user=member, is_completed=False).count()
            marker = "  ← без начислений" if member in idle else ""
            self.stdout.write(
                f"  {member.rating_current:>5}  {name:<30} квестов закрыто {member.quests_done}, "
                f"в работе {pending}{marker}"
            )
