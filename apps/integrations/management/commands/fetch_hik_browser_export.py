"""Download Hik Connect attendance XLSX via browser bot and import into HikEvent pipeline."""

from __future__ import annotations

from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.integrations.services.hik_browser_export import HikBrowserExportError, fetch_hik_xlsx_for_date
from apps.integrations.services.hik_browser_import import import_hik_export_file
from apps.integrations.services.hik_browser_settings import browser_export_enabled, hik_browser_config_from_settings


class Command(BaseCommand):
    help = (
        "Login to Hik Connect web portal (Playwright), export attendance XLSX, "
        "save HikSnapshot and process HikEvent → ExternalEvent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="snapshot_date",
            type=str,
            default="",
            help="Date ISO (YYYY-MM-DD). Default: today.",
        )
        parser.add_argument("--yesterday", action="store_true", help="Export for yesterday.")
        parser.add_argument("--debug", action="store_true", help="Save screenshot on failure.")
        parser.add_argument(
            "--skip-process",
            action="store_true",
            help="Only download + snapshot, skip ExternalEvent/penalties.",
        )
        parser.add_argument(
            "--download-only",
            action="store_true",
            help="Only download file path to stdout, do not import.",
        )
        parser.add_argument(
            "--verify-quests",
            action="store_true",
            help="After import run verify_auto_quests (daily).",
        )

    def handle(self, *args, **options):
        if not browser_export_enabled() and not options.get("debug"):
            self.stdout.write(
                self.style.WARNING(
                    "HIK_USE_BROWSER_EXPORT=0 and HIK_DATA_MODE!=browser. "
                    "Set HIK_DATA_MODE=browser or HIK_USE_BROWSER_EXPORT=1 in .env"
                )
            )

        target = self._resolve_date(options)
        config = hik_browser_config_from_settings(debug=bool(options.get("debug")))
        if not config.email or not config.password:
            raise CommandError("Set HIK_WEB_EMAIL and HIK_WEB_PASSWORD in .env")

        self.stdout.write(self.style.NOTICE(f"Fetching Hik export for {target.isoformat()} ..."))
        try:
            path = fetch_hik_xlsx_for_date(config, target)
        except HikBrowserExportError as e:
            raise CommandError(str(e)) from e

        self.stdout.write(self.style.SUCCESS(f"Downloaded: {path}"))
        if options.get("download_only"):
            return

        result = import_hik_export_file(path, target, skip_process=bool(options.get("skip_process")))
        self.stdout.write(self.style.SUCCESS(str(result)))

        if options.get("verify_quests") and not options.get("skip_process"):
            from django.core.management import call_command

            call_command("verify_quests", period="daily")

    def _resolve_date(self, options) -> date:
        if options.get("yesterday"):
            return timezone.localdate() - timedelta(days=1)
        raw = (options.get("snapshot_date") or "").strip()
        if raw:
            return date.fromisoformat(raw)
        return timezone.localdate()
