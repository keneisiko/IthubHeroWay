"""Ручной запуск той же логики, что и задача Celery fetch_hik_events."""

from django.core.management.base import BaseCommand

from apps.integrations.tasks import fetch_hik_events


class Command(BaseCommand):
    help = "Подтянуть события HikCentral и выпустить ExternalEvent (если включено HIK_FETCH_ENABLED)."

    def handle(self, *args, **options):
        msg = fetch_hik_events()
        self.stdout.write(self.style.NOTICE(msg))
