"""Ручной запуск: в режиме api — как Celery fetch_hik_events; в snapshot — обработка очереди."""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.integrations.tasks import fetch_hik_events, process_hik_events_daily


class Command(BaseCommand):
    help = (
        "Hik: api — подтянуть из HikCentral; snapshot — обработать HikEvent/очередь. "
        "Для импорта JSON используйте pull_hik_attendance."
    )

    def handle(self, *args, **options):
        mode = getattr(settings, "HIK_DATA_MODE", "snapshot")
        self.stdout.write(self.style.NOTICE(f"HIK_DATA_MODE={mode}"))
        if mode == "snapshot":
            self.stdout.write(
                "Подсказка: загрузите снимок через "
                "`python manage.py pull_hik_attendance --from-file ...` или `--synthetic`"
            )
        msg = fetch_hik_events()
        self.stdout.write(self.style.NOTICE(f"fetch: {msg}"))
        daily = process_hik_events_daily()
        self.stdout.write(self.style.NOTICE(f"daily: {daily}"))
