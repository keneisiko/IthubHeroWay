"""Тестовые заявки на подтверждение квестов.

Очередь куратора проверить нечем: студенты в закрытом прогоне не заходят и
заявок не подают. Команда заводит их от лица студентов отряда — чтобы куратор
увидел живой список, открыл ссылки и нажал «одобрить».

Данные помечены как тестовые и снимаются флагом --clear.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, Squad, User
from apps.quests.models import (
    Quest,
    QuestType,
    SelfReportProof,
    SelfReportProofStatus,
    UserQuestProgress,
)

MARKER = "[тестовая заявка]"

SAMPLES = [
    ("Сдал лабораторную по сетям, отчёт в репозитории", "https://github.com/example/lab-networks"),
    ("Доделал мини-проект: авторизация и роли", "https://github.com/example/mini-project"),
    ("Выступил с докладом на паре по архитектуре", "https://disk.example.ru/presentation.pdf"),
    ("Помогал на дне открытых дверей, провёл экскурсию", "https://vk.com/example/photo123"),
    ("Разобрал с одногруппником тему по алгоритмам", "https://t.me/example/chat"),
    ("Закрыл задачу в учебном репозитории", "https://github.com/example/commit/abc123"),
    ("Дневник практики за первую неделю", "https://disk.example.ru/practice-diary.docx"),
]


class Command(BaseCommand):
    help = "Создать тестовые заявки на подтверждение для отряда"

    def add_arguments(self, parser):
        parser.add_argument("squad_code", type=str, help="Код отряда, например itr2-24")
        parser.add_argument("--count", type=int, default=5, help="Сколько заявок создать")
        parser.add_argument("--clear", action="store_true", help="Удалить ранее созданные тестовые заявки")

    def handle(self, *args, **options):
        code = options["squad_code"].strip()
        squad = Squad.objects.filter(code=code).first()
        if squad is None:
            available = ", ".join(Squad.objects.values_list("code", flat=True)) or "нет ни одного"
            raise CommandError(f"Отряд {code!r} не найден. Доступные: {available}")

        if options["clear"]:
            self._clear(squad)
            return

        students = list(User.objects.filter(squad=squad, role=Role.AGENT).order_by("id"))
        if not students:
            raise CommandError(f"В отряде {squad.code} нет студентов — сначала импорт группы")

        quests = list(
            Quest.objects.filter(
                is_active=True, quest_type__in=[QuestType.SELF_REPORT, QuestType.LONG, QuestType.WEEKLY]
            ).order_by("id")
        )
        if not quests:
            raise CommandError("Нет подходящих квестов — сначала sync_quest_templates")

        count = max(1, int(options["count"]))
        created = 0
        with transaction.atomic():
            # Пары «студент + квест» не повторяются: на прогресс приходится
            # ровно одна заявка, второй раз база её не примет.
            for index in range(count):
                student = students[index % len(students)]
                quest = quests[(index // len(students) + index) % len(quests)]
                progress, _ = UserQuestProgress.objects.get_or_create(user=student, quest=quest)
                if SelfReportProof.objects.filter(quest_progress=progress).exists():
                    continue
                comment, link = SAMPLES[index % len(SAMPLES)]
                SelfReportProof.objects.create(
                    quest=quest,
                    user=student,
                    quest_progress=progress,
                    comment=f"{MARKER} {comment}",
                    attachment_link=link,
                    status=SelfReportProofStatus.PENDING,
                )
                created += 1

        pending = SelfReportProof.objects.filter(
            user__squad=squad, status=SelfReportProofStatus.PENDING
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Создано заявок: {created}. Всего ждут проверки в отряде {squad.code}: {pending}. "
                "Проверять: /admin/quests/selfreportproof/?status__exact=pending"
            )
        )

    def _clear(self, squad: Squad) -> None:
        doomed = SelfReportProof.objects.filter(user__squad=squad, comment__startswith=MARKER)
        total = doomed.count()
        # Прогресс и начисления, если заявку успели одобрить, остаются:
        # удаление заявки не должно тихо отбирать у студента рейтинг.
        doomed.delete()
        self.stdout.write(self.style.SUCCESS(f"Удалено тестовых заявок: {total}"))
