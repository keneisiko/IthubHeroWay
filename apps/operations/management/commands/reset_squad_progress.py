"""Сбросить прогресс отряда к чистому старту.

Первый прогон на живой группе шёл со старыми проверками: недельный квест
на КТ закрывался у всех по темам прошлых курсов, а посещаемость считалась
стопроцентной, пока занятий не было. Начисленное этими проверками надо снять,
иначе пилот стартует с неверного баланса.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from apps.accounts.models import Role, Squad, User
from apps.progress.models import LXPTopicState, RatingLog
from apps.quests.models import QuestRewardTransaction, SelfReportProof, UserQuestProgress

DEFAULT_START_RATING = User._meta.get_field("rating_current").default


class Command(BaseCommand):
    help = "Снять начисления и прогресс квестов у отряда, вернув стартовый рейтинг"

    def add_arguments(self, parser):
        parser.add_argument("squad_code", type=str, help="Код отряда")
        parser.add_argument("--dry-run", action="store_true", help="Показать, что снимется, ничего не меняя")
        parser.add_argument(
            "--keep-baseline",
            action="store_true",
            help="Не трогать зафиксированное состояние тем LXP (по умолчанию оно сбрасывается вместе с прогрессом)",
        )

    def handle(self, *args, **options):
        code = options["squad_code"].strip()
        squad = Squad.objects.filter(code=code).first()
        if squad is None:
            raise CommandError(f"Отряд {code!r} не найден")

        members = User.objects.filter(squad=squad, role=Role.AGENT)
        if not members.exists():
            raise CommandError(f"В отряде {squad.code} нет агентов")

        logs = RatingLog.objects.filter(user__in=members)
        rewards = QuestRewardTransaction.objects.filter(user__in=members)
        progress = UserQuestProgress.objects.filter(user__in=members)
        proofs = SelfReportProof.objects.filter(user__in=members)

        self.stdout.write(f"Отряд {squad.code} «{squad.name}»: {members.count()} агентов")
        self.stdout.write(
            f"Снимется: записей рейтинга {logs.count()} "
            f"(на {logs.aggregate(s=Sum('delta'))['s'] or 0:+d}), "
            f"наград за квесты {rewards.count()}, прогресса по квестам {progress.count()}, "
            f"заявок на подтверждение {proofs.count()}"
        )
        self.stdout.write(f"Рейтинг у всех станет {DEFAULT_START_RATING}, монеты обнулятся")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Пробный запуск: ничего не изменено"))
            return

        with transaction.atomic():
            proofs.delete()
            rewards.delete()
            progress.delete()
            logs.delete()
            if not options["keep_baseline"]:
                # Иначе темы остались бы помечены baseline от старого снимка,
                # и первые настоящие переходы прошли бы мимо начислений.
                LXPTopicState.objects.filter(user__in=members).delete()
            updated = members.update(rating_current=DEFAULT_START_RATING, coins_balance=0)

        self.stdout.write(
            self.style.SUCCESS(f"Сброшено агентов: {updated}. Отряд готов к чистому прогону.")
        )
