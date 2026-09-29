"""Вернуть метку первого снимка темам, закрытым до запуска платформы.

Метка терялась при каждом новом снимке, поэтому темы прошлых курсов
выглядели сданными «в дату базы» — и недельный квест на КТ засчитывался всем
и каждую неделю. Код починен, но записи в базе остались без метки: команда
проставляет её тем темам, что закрыты на момент запуска.

После неё старые темы перестают засчитываться, а всё, что студент сдаст
дальше, засчитывается как обычно.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.progress.models import LXPTopicState


class Command(BaseCommand):
    help = "Пометить уже закрытые темы как base: они сданы до запуска платформы"

    def add_arguments(self, parser):
        parser.add_argument("--squad", type=str, default="", help="Ограничить отрядом")
        parser.add_argument("--dry-run", action="store_true", help="Показать, ничего не записывая")

    def handle(self, *args, **options):
        states = LXPTopicState.objects.select_related("user")
        squad_code = (options["squad"] or "").strip()
        if squad_code:
            states = states.filter(user__squad__code=squad_code)

        touched_states = 0
        marked_topics = 0
        already_marked = 0
        open_topics = 0

        with transaction.atomic():
            for state in states:
                topics = state.topics if isinstance(state.topics, dict) else {}
                changed = False
                for entry in topics.values():
                    if not isinstance(entry, dict):
                        continue
                    if not entry.get("closed"):
                        open_topics += 1
                        continue
                    if entry.get("baseline"):
                        already_marked += 1
                        continue
                    entry["baseline"] = True
                    marked_topics += 1
                    changed = True
                if changed:
                    touched_states += 1
                    if not options["dry_run"]:
                        state.topics = topics
                        state.save(update_fields=["topics", "updated_at"])

            if options["dry_run"]:
                transaction.set_rollback(True)

        self.stdout.write(f"Студентов затронуто: {touched_states}")
        self.stdout.write(f"Тем помечено как сданные до запуска: {marked_topics}")
        self.stdout.write(f"Уже были помечены: {already_marked} | открытых тем: {open_topics}")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Пробный запуск: ничего не записано"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Готово. Прогоните verify_quests заново — недельный квест на КТ "
                    "перестанет засчитываться по темам прошлых курсов."
                )
            )
