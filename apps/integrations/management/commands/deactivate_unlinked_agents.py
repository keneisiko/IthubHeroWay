from django.core.management.base import BaseCommand

from apps.integrations.services.account_gate import deactivate_unlinked_agents


class Command(BaseCommand):
    help = (
        "Закрыть вход агентам без активной привязки Telegram. "
        "Разовая операция для баз, импортированных до того, как import_lxp_students "
        "стал создавать аккаунты неактивными."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, скольких затронет, ничего не меняя.",
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            from django.contrib.auth import get_user_model

            from apps.accounts.models import Role

            User = get_user_model()
            count = (
                User.objects.filter(role=Role.AGENT, is_active=True, is_staff=False, is_superuser=False)
                .exclude(telegram_link__is_active=True)
                .count()
            )
            self.stdout.write(self.style.NOTICE(f"Затронуло бы {count} агентов (--dry-run)."))
            return

        count = deactivate_unlinked_agents()
        self.stdout.write(self.style.SUCCESS(f"Закрыт вход у {count} агентов без привязки Telegram."))
