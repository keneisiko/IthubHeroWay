from django.core.management.base import BaseCommand
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

        target = date_cls.fromisoformat(options["date"]) if options["date"] else timezone.localdate()
        types = [t.strip() for t in options["types"].split(",") if t.strip()]
        stats = verify_all_auto_quests(target, quest_types=types)
        self.stdout.write(self.style.SUCCESS(str(stats)))
