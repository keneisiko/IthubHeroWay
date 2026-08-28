"""Match Hik export person codes to User.hik_card_code by email or callsign."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role
from apps.integrations.models import HikSnapshot
from apps.integrations.services.hik_snapshot_service import get_events_from_snapshot
from apps.integrations.services.hik_xlsx_parser import parse_hik_export_rows


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
        # Пользователи читаются один раз: раньше на каждую строку выгрузки уходило
        # два-три запроса к БД (проверка кода + поиск кандидатов), то есть N+1
        # на несколько тысяч строк.
        agents = list(User.objects.filter(role=Role.AGENT).only(
            "pk", "email", "username", "callsign", "first_name", "last_name", "hik_card_code"
        ))
        taken_codes = {(u.hik_card_code or "").strip() for u in agents if (u.hik_card_code or "").strip()}
        self.stdout.write(f"Agents with hik_card_code: {len(taken_codes)}/{len(agents)}")

        index = self._build_index(agents)

        matched = 0
        seen_codes: set[str] = set()
        for row in rows:
            code = (row.get("personCode") or "").strip()
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            if code in taken_codes:
                matched += 1
                continue
            user = self._find_user(index, row.get("personName") or row.get("name") or "")
            if user is None:
                continue
            self.stdout.write(f"  map {code} -> {user.email or user.username} ({user.callsign})")
            if options.get("apply") and not options.get("dry_run"):
                user.hik_card_code = code
                user.save(update_fields=["hik_card_code"])
            taken_codes.add(code)
            matched += 1

        self.stdout.write(self.style.SUCCESS(f"Matched codes: {matched}/{len(codes)}"))
        unmatched = [c for c in codes if c not in taken_codes]
        if unmatched:
            sample = ", ".join(unmatched[:15])
            self.stdout.write(self.style.WARNING(f"Unmatched sample: {sample}"))

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join((value or "").replace("ё", "е").replace("Ё", "Е").lower().split())

    def _build_index(self, agents: list) -> dict[str, object]:
        """Ключ (email/логин/позывной/«фамилия имя») -> пользователь; неоднозначные ключи выброшены."""
        index: dict[str, object] = {}
        ambiguous: set[str] = set()

        def add(key: str, user) -> None:
            key = self._normalize(key)
            if not key:
                return
            existing = index.get(key)
            if existing is not None and existing.pk != user.pk:
                ambiguous.add(key)
                return
            index[key] = user

        for user in agents:
            add(user.email or "", user)
            add(user.username or "", user)
            add(user.callsign or "", user)
            # Обе перестановки: в выгрузке Hik встречается и «Фамилия Имя», и «Имя Фамилия».
            if user.first_name and user.last_name:
                add(f"{user.last_name} {user.first_name}", user)
                add(f"{user.first_name} {user.last_name}", user)

        for key in ambiguous:
            index.pop(key, None)
        return index

    def _find_user(self, index: dict[str, object], raw_name: str):
        name = self._normalize(raw_name)
        if not name:
            return None
        user = index.get(name)
        if user is not None:
            return user
        # ФИО целиком («Иванов Иван Иванович») ни с first_name, ни с last_name
        # через iexact не совпадало никогда — сравниваем по фамилии и имени.
        parts = name.split()
        if len(parts) >= 2:
            return index.get(f"{parts[0]} {parts[1]}")
        return None

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
