"""Поимённые отметки посещения занятий из LXP.

Посещаемость приходила одним процентом за семестр: по нему не видно, был ли
студент на этой неделе. В занятиях группы есть отметка по каждому студенту
на каждой паре — её и сохраняем, чтобы считать пропуски по дням.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, Squad, User
from apps.integrations.services.lxp_graphql_client import LXPAuthError, LXPRequestError
from apps.integrations.services.lxp_groups import group_class_attendance
from apps.progress.models import LessonAttendance, LessonAttendanceStatus

# Что приходит из LXP: EXIST — был, EXIST_ONLINE — был онлайн,
# NOT_EXIST — не был. Отдельной отметки об опоздании в LXP нет.
STATUS_MAP = {
    "EXIST": LessonAttendanceStatus.PRESENT,
    "EXIST_ONLINE": LessonAttendanceStatus.ONLINE,
    "NOT_EXIST": LessonAttendanceStatus.MISSED,
}


def parse_moment(raw: str):
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment, timezone.utc)
    return timezone.localtime(moment)


class Command(BaseCommand):
    help = "Загрузить отметки посещения занятий группы из LXP"

    def add_arguments(self, parser):
        parser.add_argument("--group-id", type=str, required=True, help="ID учебной группы LXP")
        parser.add_argument("--squad-code", type=str, required=True, help="Код отряда в платформе")
        parser.add_argument("--weeks", type=int, default=2, help="За сколько недель забрать")
        parser.add_argument("--dry-run", action="store_true", help="Показать, ничего не записывая")

    def handle(self, *args, **options):
        squad = Squad.objects.filter(code=options["squad_code"].strip()).first()
        if squad is None:
            raise CommandError(f"Отряд {options['squad_code']!r} не найден")

        # Студент в LXP отличается от пользователя платформы: связываем по
        # lxp_user_id, проставленному при импорте группы.
        by_lxp_id = {
            str(lxp_id): user_id
            for user_id, lxp_id in User.objects.filter(squad=squad, role=Role.AGENT)
            .exclude(lxp_user_id__isnull=True)
            .exclude(lxp_user_id="")
            .values_list("id", "lxp_user_id")
        }
        if not by_lxp_id:
            raise CommandError("У студентов отряда нет lxp_user_id — сначала импорт группы")

        weeks = max(1, int(options["weeks"]))
        end = timezone.localtime()
        start = end - timedelta(weeks=weeks)

        try:
            classes = group_class_attendance(options["group_id"].strip(), start, end)
        except (LXPAuthError, LXPRequestError) as e:
            raise CommandError(f"LXP: {e}") from e
        if not classes:
            raise CommandError("Занятий за период не нашлось")

        rows = []
        statuses: Counter[str] = Counter()
        unknown_students = 0
        for item in classes:
            starts_at = parse_moment(item.get("from"))
            if not starts_at:
                continue
            discipline = ((item.get("discipline") or {}).get("name") or "").strip()
            class_id = str(item.get("id") or "").strip()
            for mark in item.get("attendance") or []:
                lxp_student = str(mark.get("studentId") or "").strip()
                user_id = by_lxp_id.get(lxp_student)
                if user_id is None:
                    unknown_students += 1
                    continue
                raw_status = str(mark.get("status") or "").strip().upper()
                status = STATUS_MAP.get(raw_status)
                statuses[raw_status] += 1
                if status is None:
                    continue
                rows.append(
                    LessonAttendance(
                        user_id=user_id,
                        lxp_class_id=class_id,
                        lesson_date=starts_at.date(),
                        starts_at=starts_at.time(),
                        discipline=discipline,
                        status=status,
                    )
                )

        self.stdout.write(f"Занятий: {len(classes)} | отметок для нашего отряда: {len(rows)}")
        self.stdout.write("Встреченные статусы: " + ", ".join(f"{k}={v}" for k, v in statuses.most_common()))
        if unknown_students:
            self.stdout.write(f"Отметок чужих студентов пропущено: {unknown_students}")
        unmapped = [s for s in statuses if s and s not in STATUS_MAP]
        if unmapped:
            self.stdout.write(
                self.style.WARNING(f"Неизвестные статусы, не сохранены: {', '.join(unmapped)}")
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Пробный запуск: ничего не записано"))
            return

        with transaction.atomic():
            saved = LessonAttendance.objects.bulk_create(
                rows,
                update_conflicts=True,
                update_fields=["lesson_date", "starts_at", "discipline", "status", "updated_at"],
                unique_fields=["user", "lxp_class_id"],
            )

        self.stdout.write(self.style.SUCCESS(f"Сохранено отметок: {len(saved)}"))
