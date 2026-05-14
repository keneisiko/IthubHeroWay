"""Проставить User.lxp_user_id по данным searchStudents LXP (для уже импортированных без id)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.integrations.management.commands.import_lxp_students import SEARCH_STUDENTS_QUERY
from apps.integrations.services.lxp_graphql_client import LXPGraphQLClient, LXPRequestError


class Command(BaseCommand):
    help = "Обновляет lxp_user_id у локальных пользователей по email из LXP (те же страницы, что и import_lxp_students)"

    def add_arguments(self, parser):
        parser.add_argument("--page-size", type=int, default=50)
        parser.add_argument("--max-pages", type=int, default=0, help="0 = все страницы")
        parser.add_argument(
            "--email-domain",
            type=str,
            default="nalchik.ithub.ru",
        )

    def handle(self, *args, **options):
        page_size = int(options["page_size"])
        max_pages = int(options["max_pages"])
        email_domain = (options["email_domain"] or "").strip().lower()
        if page_size <= 0 or page_size > 50:
            raise CommandError("--page-size must be 1..50")

        User = get_user_model()
        client = LXPGraphQLClient()
        token = client.get_token()

        updated = 0
        page = 1
        total_pages = None

        while True:
            if max_pages and page > max_pages:
                break
            try:
                response = client._post(
                    SEARCH_STUDENTS_QUERY,
                    {"input": {"page": page, "pageSize": page_size}},
                    token=token,
                    timeout=40,
                )
            except LXPRequestError as e:
                raise CommandError(f"LXP failed page {page}: {e}") from e

            if response.errors:
                raise CommandError(f"LXP GraphQL errors page {page}: {response.errors}")

            payload = (response.data or {}).get("searchStudents") or {}
            items = payload.get("items") or []
            total_pages = int(payload.get("totalPages") or total_pages or 0) or total_pages
            if not items:
                break

            for student in items:
                user_data = student.get("user") or {}
                lxp_uid = str(user_data.get("id") or "").strip()
                email = (user_data.get("email") or "").strip().lower()
                if not email.endswith(f"@{email_domain}") or not lxp_uid:
                    continue
                qs = User.objects.filter(email__iexact=email)
                if qs.filter(lxp_user_id=lxp_uid).exists():
                    continue
                n = qs.exclude(lxp_user_id=lxp_uid).update(lxp_user_id=lxp_uid)
                updated += n

            page += 1
            if total_pages and page > total_pages:
                break
            if not payload.get("hasMore"):
                break

        self.stdout.write(self.style.SUCCESS(f"backfill_lxp_user_ids: updated_rows={updated}"))
