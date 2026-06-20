from django.core.management.base import BaseCommand

from apps.integrations.services.telegram_alert import send_alert_to_admin


class Command(BaseCommand):
    help = "Отправить тестовое оповещение администратору в Telegram"

    def handle(self, *args, **options):
        ok = send_alert_to_admin(
            title="Тестовое оповещение",
            message="Если вы видите это сообщение — система алертов работает.",
            error_type="info",
            is_critical=False,
        )
        if ok:
            self.stdout.write(self.style.SUCCESS("Alert sent: True"))
        else:
            self.stdout.write(self.style.ERROR("Alert sent: False (проверьте TELEGRAM_* и TELEGRAM_ALERTS_ENABLED)"))
