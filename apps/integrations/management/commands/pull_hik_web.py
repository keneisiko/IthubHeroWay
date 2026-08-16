"""Забрать записи прохода из портала Hik напрямую по HTTP.

Замена цепочке «Playwright кликает по меню → скачивает XLSX → парсер».
Браузер используется только для получения cookies (см. `hik_session.py`).

Примеры:

    # За вчера (как ночная задача Celery)
    python manage.py pull_hik_web --yesterday

    # За конкретный день
    python manage.py pull_hik_web --date=2026-06-15

    # За период — например, чтобы проверить платформу на исторических данных,
    # пока турникеты не работают
    python manage.py pull_hik_web --from=2026-06-01 --to=2026-06-30

    # Только показать, что придёт, ничего не сохраняя
    python manage.py pull_hik_web --date=2026-06-15 --dry-run
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.integrations.models import HikImportMode, HikImportRun, HikImportStatus
from apps.integrations.services.hik_attendance_processor import (
    process_unprocessed_hik_events,
    save_hik_row_as_event,
)
from apps.integrations.services.hik_web_client import DIRECTION_ENTRY, DIRECTION_EXIT
from apps.integrations.services.hik_web_fetch import fetch_rows_for_range


def _parse_date(value: str, option: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CommandError(f"{option}: ожидается дата в формате ГГГГ-ММ-ДД, получено «{value}»") from exc


class Command(BaseCommand):
    help = "Импорт записей прохода из портала Hik Connect по внутреннему HTTP API"

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default="", help="Один день (ГГГГ-ММ-ДД)")
        parser.add_argument("--from", dest="date_from", type=str, default="", help="Начало периода")
        parser.add_argument("--to", dest="date_to", type=str, default="", help="Конец периода")
        parser.add_argument("--yesterday", action="store_true", help="За вчерашний день")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать сводку и не сохранять ничего в базу",
        )
        parser.add_argument(
            "--skip-process",
            action="store_true",
            help="Сохранить HikEvent, но не разбирать очередь (без ExternalEvent и штрафов)",
        )

    def handle(self, *args, **options):
        start_date, end_date = self._resolve_range(options)
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(start_date, time.min), tz)
        end = timezone.make_aware(datetime.combine(end_date, time.max), tz)

        self.stdout.write(f"Запрашиваю записи с {start_date} по {end_date}…")
        result = fetch_rows_for_range(start, end)

        if result.relogin_used:
            self.stdout.write(self.style.NOTICE("Сессия портала обновлена повторным входом"))

        rows = result.rows
        self._print_summary(rows)

        if not rows:
            self.stdout.write(
                self.style.WARNING(
                    "Портал не вернул ни одной записи за период. Если турникеты выключены "
                    "или колледж не работает — это ожидаемо."
                )
            )
            return

        if options["dry_run"]:
            self.stdout.write(self.style.NOTICE("--dry-run: ничего не сохранено"))
            return

        created = 0
        for row in rows:
            _, was_created = save_hik_row_as_event(row)
            if was_created:
                created += 1
        self.stdout.write(
            self.style.SUCCESS(f"Сохранено новых событий: {created} из {len(rows)}")
        )

        run = HikImportRun.objects.create(
            mode=HikImportMode.WEB_API,
            status=HikImportStatus.SUCCESS,
            date_from=start_date,
            date_to=end_date,
            records_fetched=len(rows),
            events_created=created,
            relogin_used=result.relogin_used,
        )

        if options["skip_process"]:
            self.stdout.write(self.style.NOTICE("--skip-process: очередь не разбиралась"))
            return

        seen, ext_created, skipped = process_unprocessed_hik_events(limit=50_000)
        run.external_created = ext_created
        run.users_unmatched = skipped
        run.save(update_fields=["external_created", "users_unmatched"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Обработано: {seen}, создано ExternalEvent: {ext_created}, "
                f"без сопоставленного пользователя: {skipped}"
            )
        )
        if skipped:
            self.stdout.write(
                self.style.WARNING(
                    "Часть проходов не привязана к пользователям: проверьте, что почта "
                    "студента в портале совпадает с почтой в платформе."
                )
            )

    def _resolve_range(self, options) -> tuple[date, date]:
        if options["yesterday"]:
            day = timezone.localdate() - timedelta(days=1)
            return day, day
        if options["date"]:
            day = _parse_date(options["date"], "--date")
            return day, day
        if options["date_from"] or options["date_to"]:
            if not (options["date_from"] and options["date_to"]):
                raise CommandError("--from и --to задаются вместе")
            start = _parse_date(options["date_from"], "--from")
            end = _parse_date(options["date_to"], "--to")
            if end < start:
                raise CommandError("--to не может быть раньше --from")
            return start, end
        day = timezone.localdate()
        return day, day

    def _print_summary(self, rows: list[dict]) -> None:
        entries = sum(1 for r in rows if r["direction"] == DIRECTION_ENTRY)
        exits = sum(1 for r in rows if r["direction"] == DIRECTION_EXIT)
        with_email = sum(1 for r in rows if r["personEmail"])
        auth_failed = sum(1 for r in rows if not r["authOk"])

        self.stdout.write(f"Получено записей: {len(rows)}")
        self.stdout.write(f"  входов: {entries}, выходов: {exits}")
        self.stdout.write(f"  с почтой для привязки: {with_email}")
        if auth_failed:
            self.stdout.write(f"  неуспешных проходов: {auth_failed}")
