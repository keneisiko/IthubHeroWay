"""
Тянет из LXP снимок успеваемости (JSON в LXPSnapshot) и опционально обновляет рейтинг/КТ по пользователям.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Role
from apps.integrations.lxp_task_helpers import refresh_lxp_token_sync
from apps.integrations.models import LXPSnapshot, TelegramAccountLink
from apps.integrations.services.lxp_graphql_client import (
    LXPAuthError,
    LXPGraphQLClient,
    LXPRequestError,
)
from apps.progress.services.lxp_rating_from_snapshot import apply_rating_from_lxp_snapshot

SYNTHETIC_TELEGRAM_BASE = 5_100_000_000


class Command(BaseCommand):
    help = "Загружает успеваемость из LXP (GraphQL → LXPSnapshot) и при желании применяет её к пользователям (рейтинг, unclosed_ct_count)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="snapshot_date",
            type=str,
            default="",
            help="Дата снимка ISO (YYYY-MM-DD). По умолчанию — сегодня по TIME_ZONE Django.",
        )
        parser.add_argument(
            "--yesterday",
            action="store_true",
            help="Снимок за вчера (как в Celery Beat).",
        )
        parser.add_argument(
            "--skip-rating",
            action="store_true",
            help="Только сохранить LXPSnapshot, без пересчёта RatingLog/unclosed_ct.",
        )
        parser.add_argument(
            "--synthetic-telegram-agents",
            action="store_true",
            help="ДЛЯ ТЕСТА/СТЕЙДЖА: создать фиктивные TelegramAccountLink для агентов с "
            "lxp_user_id без привязки, чтобы они попали в пересчёт рейтинга.",
        )
        parser.add_argument(
            "--quiet-meta",
            action="store_true",
            help="Меньше вывода (без дампа полного meta JSON).",
        )

    def handle(self, *args, **opts):
        if opts["yesterday"] and opts["snapshot_date"]:
            raise CommandError("Нельзя одновременно --yesterday и --date")

        today = timezone.localdate()
        if opts["yesterday"]:
            target_date = today - timedelta(days=1)
        elif opts["snapshot_date"]:
            try:
                target_date = date.fromisoformat(opts["snapshot_date"].strip())
            except ValueError as e:
                raise CommandError("Неверный формат --date, ожидается YYYY-MM-DD") from e
        else:
            target_date = today

        self.stdout.write(self.style.NOTICE(f"Дата снимка: {target_date.isoformat()}"))

        if opts["synthetic_telegram_agents"]:
            n = self._ensure_synthetic_telegram_agents()
            self.stdout.write(self.style.WARNING(f"Synthetic Telegram links created: {n}"))

        try:
            refresh_lxp_token_sync()
            client = LXPGraphQLClient()
            client.get_token()
            data = client.fetch_all_data(date=target_date)
        except LXPAuthError as e:
            raise CommandError(f"LXP auth: {e}") from e
        except LXPRequestError as e:
            raise CommandError(f"LXP GraphQL: {e}") from e

        LXPSnapshot.objects.update_or_create(date=target_date, defaults={"data": data})

        meta = data.get("meta") or {}
        grades = ((data.get("grades") or {}).get("data") or {}) if isinstance(data.get("grades"), dict) else {}
        ctr = (
            ((data.get("control_points") or {}).get("data") or {})
            if isinstance(data.get("control_points"), dict)
            else {}
        )

        self.stdout.write(self.style.SUCCESS("LXPSnapshot сохранён."))
        if not opts["quiet_meta"]:
            self.stdout.write("meta.partial=" + json.dumps(meta.get("partial")))
            self.stdout.write("meta.catalog_groups_processed=" + json.dumps(meta.get("catalog_groups_processed")))
            self.stdout.write(f"students_in_grades_slice={len(grades)} lx_users_in_control_points={len(ctr)}")
        else:
            self.stdout.write(f"partial={meta.get('partial')} groups={meta.get('catalog_groups_processed')}")

        if opts["skip_rating"]:
            self.stdout.write(self.style.WARNING("Пересчёт рейтинга пропущен (--skip-rating)."))
            return

        res = apply_rating_from_lxp_snapshot(target_date)
        self.stdout.write(
            self.style.SUCCESS(
                f"Рейтинг: рассмотрено={res.users_considered}, обновлено={res.users_updated}, "
                f"partial_snapshot={res.partial_snapshot} ({res.notes})"
            )
        )

    def _ensure_synthetic_telegram_agents(self) -> int:
        User = get_user_model()
        created = 0
        qs = User.objects.filter(role=Role.AGENT).exclude(Q(lxp_user_id__isnull=True) | Q(lxp_user_id=""))
        missing = qs.filter(telegram_link__isnull=True)
        for u in missing.iterator(chunk_size=200):
            telegram_user_id = SYNTHETIC_TELEGRAM_BASE + int(u.pk)
            TelegramAccountLink.objects.update_or_create(
                user=u,
                defaults={
                    "telegram_user_id": telegram_user_id,
                    "telegram_chat_id": telegram_user_id,
                    "telegram_username": "",
                    "is_active": True,
                },
            )
            created += 1
        return created
