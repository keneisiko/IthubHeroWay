"""Проставить направление студентам, у которых его нет, по названию группы.

Новые студенты получают трек при импорте группы; команда — для тех, кто
был заведён раньше. Повторный запуск безопасен: заданный трек не меняется.
"""

from django.core.management.base import BaseCommand

from apps.accounts.models import Role, User
from apps.accounts.tracks import assign_track_if_empty


class Command(BaseCommand):
    help = "Проставить трек студентам без трека по названию их группы."

    def handle(self, *args, **options):
        students = User.objects.filter(role=Role.AGENT, track__isnull=True).exclude(squad=None)
        assigned = sum(
            assign_track_if_empty(user, user.squad.name) for user in students.select_related("squad")
        )
        left = User.objects.filter(role=Role.AGENT, track__isnull=True).count()
        self.stdout.write(f"Трек проставлен: {assigned}. Без трека осталось: {left}.")
