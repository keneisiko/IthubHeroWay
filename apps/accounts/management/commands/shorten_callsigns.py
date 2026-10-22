"""Заменить служебные позывные импорта на «Имя Ф.».

Свой позывной студента не трогается: меняются только пустые, совпадающие
с началом логина и «lxp_…». Повторный запуск безопасен. По умолчанию —
пробный прогон; изменить базу — с флагом --apply.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.callsigns import default_callsign, is_auto_callsign
from apps.accounts.models import Role, User


class Command(BaseCommand):
    help = "Короткие позывные «Имя Ф.» вместо служебных из импорта."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записать изменения в базу.")

    def handle(self, *args, **options):
        apply = options["apply"]
        changed = 0
        with transaction.atomic():
            for user in User.objects.filter(role=Role.AGENT).order_by("pk"):
                if not is_auto_callsign(user):
                    continue
                new = default_callsign(user.first_name, user.last_name, fallback=user.callsign, exclude_pk=user.pk)
                if new == user.callsign:
                    continue
                if changed < 5:
                    self.stdout.write(f"{user.callsign} → {new}")
                if apply:
                    user.callsign = new
                    user.save(update_fields=["callsign"])
                changed += 1
            if not apply:
                transaction.set_rollback(True)
        mode = "Изменено" if apply else "Будет изменено (пробный прогон, --apply чтобы записать)"
        self.stdout.write(f"{mode}: {changed}.")
