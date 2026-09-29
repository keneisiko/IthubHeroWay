"""Расписание отряда из занятий LXP.

Без расписания дедлайн «Утреннего чек-ина» был общим — 10:00 для всех, — и
студент, у которого первая пара в 12:50, получал опоздание, придя вовремя.
А расчёт серий считал учебными все будни подряд, включая дни без пар.

Занятия приходят с временем в UTC; в расписание кладём местное время, по
нему платформа и сверяет проходы через турникет.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Squad
from apps.integrations.services.lxp_graphql_client import LXPAuthError, LXPRequestError
from apps.integrations.services.lxp_groups import group_classes
from apps.schedule.models import Schedule

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


def parse_moment(raw: str):
    """Время занятия из LXP в местное время платформы."""
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
    help = "Загрузить расписание отряда из занятий LXP"

    def add_arguments(self, parser):
        parser.add_argument("--group-id", type=str, required=True, help="ID учебной группы LXP")
        parser.add_argument("--squad-code", type=str, required=True, help="Код отряда в платформе")
        parser.add_argument("--weeks", type=int, default=2, help="За сколько недель смотреть занятия")
        parser.add_argument("--replace", action="store_true", help="Сначала удалить прежнее расписание")
        parser.add_argument("--dry-run", action="store_true", help="Показать, ничего не записывая")

    def handle(self, *args, **options):
        squad = Squad.objects.filter(code=options["squad_code"].strip()).first()
        if squad is None:
            available = ", ".join(Squad.objects.values_list("code", flat=True)) or "нет ни одного"
            raise CommandError(f"Отряд не найден. Доступные: {available}")

        weeks = max(1, int(options["weeks"]))
        end = timezone.localtime()
        start = end - timedelta(weeks=weeks)

        try:
            classes = group_classes(options["group_id"].strip(), start, end)
        except (LXPAuthError, LXPRequestError) as e:
            raise CommandError(f"LXP: {e}") from e
        if not classes:
            raise CommandError("Занятий за период не нашлось — проверьте --group-id и --weeks")

        # Пара повторяется каждую неделю, поэтому слоты складываются в набор:
        # день недели + начало + конец. Дисциплина берётся первой встреченной.
        slots: dict[tuple[int, object, object], str] = {}
        seen_by_day: dict[int, int] = defaultdict(int)
        for item in classes:
            starts_at = parse_moment(item.get("from"))
            ends_at = parse_moment(item.get("to"))
            if not starts_at or not ends_at:
                continue
            discipline = ((item.get("discipline") or {}).get("name") or "").strip()
            key = (starts_at.weekday(), starts_at.time(), ends_at.time())
            slots.setdefault(key, discipline)
            seen_by_day[starts_at.weekday()] += 1

        if not slots:
            raise CommandError("У занятий не оказалось времени начала — расписание не построить")

        self.stdout.write(f"Занятий за {weeks} нед.: {len(classes)} | уникальных пар в неделе: {len(slots)}")
        for (weekday, start_time, end_time), discipline in sorted(slots.items()):
            self.stdout.write(
                f"  {WEEKDAYS[weekday]:12} {start_time:%H:%M}–{end_time:%H:%M}  {discipline[:50]}"
            )
        first_by_day = {}
        for (weekday, start_time, _), _discipline in slots.items():
            if weekday not in first_by_day or start_time < first_by_day[weekday]:
                first_by_day[weekday] = start_time
        self.stdout.write("Первая пара по дням:")
        for weekday in sorted(first_by_day):
            self.stdout.write(f"  {WEEKDAYS[weekday]:12} {first_by_day[weekday]:%H:%M}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Пробный запуск: ничего не записано"))
            return

        with transaction.atomic():
            removed = 0
            if options["replace"]:
                removed, _ = Schedule.objects.filter(squad=squad).delete()
            created = updated = 0
            for (weekday, start_time, end_time), discipline in slots.items():
                slot, was_created = Schedule.objects.update_or_create(
                    squad=squad,
                    day_of_week=weekday,
                    start_time=start_time,
                    defaults={"end_time": end_time, "discipline": discipline, "is_active": True},
                )
                created += int(was_created)
                updated += int(not was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Расписание отряда {squad.code}: создано {created}, обновлено {updated}"
                + (f", удалено прежних {removed}" if options["replace"] else "")
            )
        )
