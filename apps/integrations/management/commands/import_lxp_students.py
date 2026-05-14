from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role
from apps.integrations.services.lxp_graphql_client import LXPGraphQLClient, LXPRequestError


SEARCH_STUDENTS_QUERY = """
query ImportStudents($input: SearchStudentsInput!) {
  searchStudents(input: $input) {
    total
    totalPages
    page
    perPage
    hasMore
    items {
      id
      user {
        id
        email
        firstName
        lastName
        middleName
      }
    }
  }
}
"""


def _sanitize_identifier(raw: str, fallback: str) -> str:
    value = (raw or "").strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "_", value)
    value = value.strip("._-")
    return value[:50] or fallback


class Command(BaseCommand):
    help = "Import students from LXP GraphQL into local accounts_user table"

    def add_arguments(self, parser):
        parser.add_argument("--page-size", type=int, default=50, help="LXP page size per request (max/default: 50)")
        parser.add_argument(
            "--max-pages",
            type=int,
            default=0,
            help="Max pages to process (0 = all available pages)",
        )
        parser.add_argument(
            "--email-domain",
            type=str,
            default="nalchik.ithub.ru",
            help="Import only users with this email domain (default: nalchik.ithub.ru)",
        )

    def handle(self, *args, **options):
        page_size = int(options["page_size"])
        max_pages = int(options["max_pages"])
        email_domain = (options["email_domain"] or "").strip().lower()
        if page_size <= 0:
            raise CommandError("--page-size must be > 0")
        if page_size > 50:
            raise CommandError("--page-size must be <= 50")
        if max_pages < 0:
            raise CommandError("--max-pages must be >= 0")
        if not email_domain:
            raise CommandError("--email-domain must not be empty")

        client = LXPGraphQLClient()
        token = client.get_token()
        User = get_user_model()

        page = 1
        created_total = 0
        updated_total = 0
        seen_total = 0
        skipped_domain_total = 0
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
                raise CommandError(f"LXP request failed on page {page}: {e}") from e

            if response.errors:
                raise CommandError(f"LXP GraphQL errors on page {page}: {response.errors}")

            payload = (response.data or {}).get("searchStudents") or {}
            items = payload.get("items") or []
            total_pages = int(payload.get("totalPages") or total_pages or 0) or total_pages
            has_more = bool(payload.get("hasMore"))

            if not items:
                break

            for student in items:
                seen_total += 1
                student_id = str(student.get("id") or "")
                user_data = student.get("user") or {}
                lxp_user_id = str(user_data.get("id") or student_id or "")
                email = (user_data.get("email") or "").strip().lower()
                first_name = (user_data.get("firstName") or "").strip()
                last_name = (user_data.get("lastName") or "").strip()
                if not email.endswith(f"@{email_domain}"):
                    skipped_domain_total += 1
                    continue

                base_slug = _sanitize_identifier(
                    email.split("@", 1)[0] if email else lxp_user_id,
                    fallback="student",
                )
                username = f"{base_slug}_{lxp_user_id[:8]}" if lxp_user_id else base_slug
                username = username[:150]
                callsign = f"lxp_{lxp_user_id[:12]}" if lxp_user_id else f"lxp_{base_slug}"
                callsign = callsign[:50]

                instance = None
                if email:
                    instance = User.objects.filter(email__iexact=email).first()

                if instance:
                    changed_fields: list[str] = []
                    if first_name and instance.first_name != first_name:
                        instance.first_name = first_name
                        changed_fields.append("first_name")
                    if last_name and instance.last_name != last_name:
                        instance.last_name = last_name
                        changed_fields.append("last_name")
                    if instance.role != Role.AGENT:
                        instance.role = Role.AGENT
                        changed_fields.append("role")
                    if lxp_user_id and instance.lxp_user_id != lxp_user_id:
                        instance.lxp_user_id = lxp_user_id
                        changed_fields.append("lxp_user_id")
                    if changed_fields:
                        instance.save(update_fields=changed_fields)
                        updated_total += 1
                    continue

                # Resolve username conflicts.
                candidate_username = username or f"student_{seen_total}"
                suffix = 1
                while User.objects.filter(username=candidate_username).exists():
                    candidate_username = f"{candidate_username[:140]}_{suffix}"[:150]
                    suffix += 1

                # Resolve callsign conflicts.
                candidate_callsign = callsign or f"lxp_student_{seen_total}"
                cs_suffix = 1
                while User.objects.filter(callsign=candidate_callsign).exists():
                    candidate_callsign = f"{candidate_callsign[:45]}_{cs_suffix}"[:50]
                    cs_suffix += 1

                created = User.objects.create(
                    username=candidate_username,
                    callsign=candidate_callsign,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    role=Role.AGENT,
                    is_active=True,
                    status="imported_lxp",
                    lxp_user_id=lxp_user_id or None,
                )
                created.set_unusable_password()
                created.save(update_fields=["password"])
                created_total += 1

            self.stdout.write(
                self.style.NOTICE(
                    f"Processed page {page} ({len(items)} items). "
                    f"Created={created_total}, Updated={updated_total}, SkippedByDomain={skipped_domain_total}"
                )
            )

            page += 1
            if total_pages and page > total_pages:
                break
            if not has_more and (not total_pages or page > total_pages):
                break

        self.stdout.write(
            self.style.SUCCESS(
                f"Import completed. Seen={seen_total}, Created={created_total}, Updated={updated_total}, "
                f"SkippedByDomain={skipped_domain_total}, Domain=@{email_domain}, "
                f"Pages={page - 1}"
            )
        )

