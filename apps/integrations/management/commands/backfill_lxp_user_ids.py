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
        parser.add_argument("--max-pages", type=int, default=0, help="Ограничение числа страниц; 0 = все страницы")
        parser.add_argument(
            "--email-domain",
            type=str,
            default="nalchik.ithub.ru",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет изменено, ничего не записывать.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Перезаписывать уже заполненный lxp_user_id, если он отличается от полученного из LXP.",
        )

    def handle(self, *args, **options):
        page_size = int(options["page_size"])
        max_pages = int(options["max_pages"])
        email_domain = (options["email_domain"] or "").strip().lower()
        dry_run = bool(options.get("dry_run"))
        overwrite = bool(options.get("overwrite"))
        if page_size <= 0 or page_size > 50:
            raise CommandError("--page-size должен быть в диапазоне 1..50")
        if max_pages < 0:
            raise CommandError("--max-pages не может быть отрицательным (0 = все страницы)")

        User = get_user_model()
        client = LXPGraphQLClient()
        token = client.get_token()

        updated = 0
        conflicts = 0
        pages_done = 0
        page = 1

        while True:
            try:
                # Публичного метода для произвольного GraphQL-запроса у клиента нет:
                # _cached_query/_safe_cached_query тоже приватные и кэшируют ответ,
                # что для бэкфилла нежелательно.
                response = client._post(
                    SEARCH_STUDENTS_QUERY,
                    {"input": {"page": page, "pageSize": page_size}},
                    token=token,
                    timeout=40,
                )
            except LXPRequestError as e:
                raise CommandError(f"Ошибка запроса к LXP на странице {page}: {e}") from e

            if response.errors:
                raise CommandError(f"LXP вернул GraphQL-ошибки на странице {page}: {response.errors}")

            payload = (response.data or {}).get("searchStudents") or {}
            items = payload.get("items") or []
            if not items:
                break

            for student in items:
                user_data = student.get("user") or {}
                lxp_uid = str(user_data.get("id") or "").strip()
                email = (user_data.get("email") or "").strip().lower()
                if not email.endswith(f"@{email_domain}") or not lxp_uid:
                    continue

                # Раньше здесь был qs.exclude(...).update(...): один UPDATE менял
                # lxp_user_id сразу у всех пользователей с этим email, включая тех,
                # у кого уже был проставлен другой id. Теперь решение принимается
                # по каждой записи отдельно.
                for user in User.objects.filter(email__iexact=email).only("pk", "username", "lxp_user_id"):
                    current = (user.lxp_user_id or "").strip()
                    if current == lxp_uid:
                        continue
                    if current and not overwrite:
                        conflicts += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"  пропуск {user.username} ({email}): уже задан lxp_user_id={current}, "
                                f"в LXP {lxp_uid}; для замены запустите с --overwrite"
                            )
                        )
                        continue
                    action = "будет задан" if dry_run else "задан"
                    self.stdout.write(f"  {user.username} ({email}): {action} lxp_user_id {current or '—'} -> {lxp_uid}")
                    if not dry_run:
                        User.objects.filter(pk=user.pk).update(lxp_user_id=lxp_uid)
                    updated += 1

            pages_done += 1
            # Единственная точка выхода по пагинации: раньше три независимых
            # условия (пустой items, totalPages, hasMore) конкурировали между собой
            # и часть страниц могла быть пропущена. totalPages точнее hasMore,
            # поэтому он приоритетнее; hasMore — запасной вариант.
            total_pages = int(payload.get("totalPages") or 0)
            if total_pages:
                if page >= total_pages:
                    break
            elif not payload.get("hasMore"):
                break
            if max_pages and pages_done >= max_pages:
                break
            page += 1

        prefix = "backfill_lxp_user_ids (dry-run)" if dry_run else "backfill_lxp_user_ids"
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}: страниц={pages_done}, изменений={updated}, конфликтов={conflicts}"
            )
        )
