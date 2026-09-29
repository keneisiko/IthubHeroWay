"""Повторная связка сохранённых проходов со студентами.

Проходы приходят раньше, чем становится известно, кому они принадлежат:
почты в портале личные, и связка идёт по кодам, которые проставляет
link_hik_persons. После неё уже сохранённые события нужно разобрать заново —
раньше для этого приходилось лезть в shell, а `sync_hik_events` в режиме
browser вместо этого уходил кликать по меню портала.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.integrations.models import HikEvent
from apps.integrations.services.hik_attendance_processor import process_unprocessed_hik_events


class Command(BaseCommand):
    help = "Разобрать сохранённые проходы Hik заново (после link_hik_persons)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-unmatched",
            action="store_true",
            help="Сбросить только те, что остались без владельца (по умолчанию — все обработанные)",
        )
        parser.add_argument("--limit", type=int, default=20000, help="Сколько событий разобрать")

    def handle(self, *args, **options):
        queryset = HikEvent.objects.filter(processed=True)
        if options["only_unmatched"]:
            # Событие без студента отмечено как обработанное, но пользы
            # не принесло: только такие и имеет смысл трогать повторно.
            queryset = queryset.filter(student_code="")

        reset = queryset.update(processed=False, last_error="")
        self.stdout.write(f"Снята отметка обработки: {reset}")

        seen, created, skipped = process_unprocessed_hik_events(limit=int(options["limit"]))
        self.stdout.write(
            self.style.SUCCESS(
                f"Рассмотрено: {seen}, создано событий посещаемости: {created}, "
                f"без сопоставленного студента: {skipped}"
            )
        )
        if skipped and not created:
            self.stdout.write(
                self.style.WARNING(
                    "Ни один проход не связан: проверьте коды в карточках — "
                    "manage.py link_hik_persons --squad <код> --apply"
                )
            )
