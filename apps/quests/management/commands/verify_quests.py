from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.quests.services.quest_verification import verify_all_auto_quests


class Command(BaseCommand):
    help = "Run auto-verification for quests (daily + weekly)."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default="", help="YYYY-MM-DD (default: today)")
        parser.add_argument(
            "--types",
            type=str,
            default="daily,weekly",
            help="Comma-separated quest types",
        )

    def handle(self, *args, **options):
        from datetime import date as date_cls

        raw_date = (options["date"] or "").strip()
        if raw_date:
            # Без обработки ValueError кривая дата в аргументе давала пользователю
            # трейсбек вместо понятного сообщения команды.
            try:
                target = date_cls.fromisoformat(raw_date)
            except ValueError as e:
                raise CommandError(f"Некорректная дата --date={raw_date!r}, ожидается формат YYYY-MM-DD") from e
        else:
            target = timezone.localdate()
        types = [t.strip() for t in options["types"].split(",") if t.strip()]
        stats = verify_all_auto_quests(target, quest_types=types)
        self.stdout.write(self.style.SUCCESS(str(stats)))
