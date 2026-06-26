"""Match Hik export person codes to User.hik_card_code by email or callsign."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.accounts.models import Role
from apps.integrations.models import HikSnapshot
from apps.integrations.services.hik_snapshot_service import get_events_from_snapshot
from apps.integrations.services.hik_xlsx_parser import load_tabular_rows, parse_hik_export_rows


class Command(BaseCommand):
    help = (
        "Inspect Hik XLSX/snapshot codes and optionally assign hik_card_code to agents "
        "when email/callsign matches person name in export."
    )

    def add_arguments(self, parser):
        parser.add_argument("--from-xlsx", type=str, default="", help="Path to XLSX export.")
        parser.add_argument(
            "--from-snapshot-date",
            type=str,
            default="",
            help="Use HikSnapshot for ISO date instead of file.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write hik_card_code when unique email/callsign match found in export row.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Only print mapping report.")

    def handle(self, *args, **options):
        rows = self._load_rows(options)
        if not rows:
            raise CommandError("No events found in export.")

        codes = sorted({(r.get("personCode") or "").strip() for r in rows if (r.get("personCode") or "").strip()})
        self.stdout.write(self.style.NOTICE(f"Unique person codes in export: {len(codes)}"))

        User = get_user_model()
        agents = User.objects.filter(role=Role.AGENT)
        with_code = agents.exclude(hik_card_code="").exclude(hik_card_code__isnull=True).count()
        self.stdout.write(f"Agents with hik_card_code: {with_code}/{agents.count()}")

        matched = 0
        for row in rows:
            code = (row.get("personCode") or "").strip()
            if not code:
                continue
            if agents.filter(hik_card_code=code).exists():
                matched += 1
                continue
            name = (row.get("personName") or row.get("name") or "").strip().lower()
            if not name:
                continue
            candidates = agents.filter(
                Q(email__iexact=name)
                | Q(callsign__iexact=name)
                | Q(username__iexact=name)
                | Q(first_name__iexact=name)
                | Q(last_name__iexact=name)
            )
            if candidates.count() != 1:
                continue
            user = candidates.first()
            self.stdout.write(f"  map {code} -> {user.email or user.username} ({user.callsign})")
            if options.get("apply") and not options.get("dry_run"):
                user.hik_card_code = code
                user.save(update_fields=["hik_card_code"])
            matched += 1

        self.stdout.write(self.style.SUCCESS(f"Matched codes: {matched}/{len(codes)}"))
        unmatched = [c for c in codes if not agents.filter(hik_card_code=c).exists()]
        if unmatched:
            sample = ", ".join(unmatched[:15])
            self.stdout.write(self.style.WARNING(f"Unmatched sample: {sample}"))

    def _load_rows(self, options) -> list[dict]:
        xlsx = (options.get("from_xlsx") or "").strip()
        snap_date = (options.get("from_snapshot_date") or "").strip()
        if xlsx:
            from datetime import date

            return parse_hik_export_rows(xlsx, fallback_date=date.today())
        if snap_date:
            from datetime import date

            snap = HikSnapshot.objects.filter(date=date.fromisoformat(snap_date)).first()
            if not snap:
                raise CommandError(f"No HikSnapshot for {snap_date}")
            return get_events_from_snapshot(snap)
        raise CommandError("Provide --from-xlsx or --from-snapshot-date")
