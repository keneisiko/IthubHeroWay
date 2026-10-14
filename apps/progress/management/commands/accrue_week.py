"""Недельное начисление по разделам 3 и 4 Положения.

    python manage.py accrue_week                 # прошедшая неделя
    python manage.py accrue_week --week 2026-10-19
    python manage.py accrue_week --since 2026-10-19   # добрать все недели
    python manage.py accrue_week --dry-run
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.integrations.services.account_gate import agents_for_scoring
from apps.progress.services.polozhenie_academic import (
    components_for_user,
    run_weekly_accrual,
    snapshot_ct_data,
    topic_breakdown,
)
from apps.progress.services.polozhenie_awards import run_weekly_roles
from apps.progress.services.polozhenie_period import (
    is_payable_week,
    period_key,
    season_start_date,
    week_end,
    week_start,
)


class Command(BaseCommand):
    help = "Начисляет рейтинг и монеты за учебную неделю по Положению (разделы 3 и 4)."

    def add_arguments(self, parser):
        parser.add_argument("--week", type=str, default="", help="Любая дата внутри недели (ГГГГ-ММ-ДД).")
        parser.add_argument(
            "--since",
            type=str,
            default="",
            help="Начислить все недели начиная с этой даты по прошедшую включительно.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Показать расчёт, ничего не начисляя.")

    def handle(self, *args, **options):
        if options["week"] and options["since"]:
            raise CommandError("--week и --since вместе не используются.")

        today = timezone.localdate()
        last_finished_week = today - timedelta(days=7)

        if options["since"]:
            try:
                start_day = date.fromisoformat(options["since"])
            except ValueError as exc:
                raise CommandError(f"Неверная дата: {options['since']}") from exc
            days = []
            cursor = week_start(start_day)
            while cursor <= week_start(last_finished_week):
                days.append(cursor)
                cursor += timedelta(days=7)
        elif options["week"]:
            try:
                days = [date.fromisoformat(options["week"])]
            except ValueError as exc:
                raise CommandError(f"Неверная дата: {options['week']}") from exc
        else:
            days = [last_finished_week]

        if options["dry_run"]:
            for day in days:
                self._preview(day)
            return

        for day in days:
            academic = run_weekly_accrual(day)
            if academic.notes == "before_season_start":
                self.stdout.write(
                    self.style.WARNING(
                        f"{academic.period}: неделя до старта сезона "
                        f"({season_start_date().isoformat()}), начислений нет."
                    )
                )
                continue
            roles = run_weekly_roles(day)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{academic.period} ({academic.week_start}–{academic.week_end}): "
                    f"учтено {academic.users_considered}, начислено {academic.users_paid}; "
                    f"рейтинг +{academic.rating_total}, монеты +{academic.coins_total}; "
                    f"отложено КТ {academic.deferred_ct}, посещаемость {academic.deferred_attendance}; "
                    f"роли: {roles['paid']} чел., рейтинг +{roles['rating']}, монеты +{roles['coins']}"
                )
            )

    def _preview(self, day: date) -> None:
        start, end = week_start(day), week_end(day)
        key = period_key(start)
        if not is_payable_week(start):
            self.stdout.write(
                self.style.WARNING(f"{key}: до старта сезона {season_start_date().isoformat()}, пропуск.")
            )
            return

        ct_data = snapshot_ct_data(start, end)
        self.stdout.write(f"\n{key}: {start} – {end} (снимок: {len(ct_data)} студентов)")
        self.stdout.write(
            f"{'Студент':<28}{'КТ %':>8}{'сдано':>7}{'не сдано':>10}"
            f"{'проверка':>10}{'будущих':>9}{'Пос. %':>9}{'Б':>8}"
        )
        shown = 0
        audience = agents_for_scoring(User.objects.filter(role=Role.AGENT))
        for user in audience.select_related("squad").order_by("id")[:200]:
            parts = components_for_user(user, start, end, ct_data)
            if parts.ct_percent is None and parts.attendance_percent is None:
                continue
            academic = getattr(settings, "POLOZHENIE_ACADEMIC", {})
            total = Decimal("0")
            if parts.ct_percent is not None:
                total += Decimal(str(academic["CT_WEEKLY_MAX"])) * parts.ct_percent / 100
            if parts.attendance_percent is not None:
                total += Decimal(str(academic["ATTENDANCE_WEEKLY_MAX"])) * parts.attendance_percent / 100
            ct_text = "—" if parts.ct_percent is None else f"{parts.ct_percent}"
            att_text = "—" if parts.attendance_percent is None else f"{parts.attendance_percent}"
            counts = topic_breakdown(ct_data.get((user.lxp_user_id or "").strip()) or {})
            name = (user.get_full_name() or user.username)[:27]
            self.stdout.write(
                f"{name:<28}{ct_text:>8}{counts['passed']:>7}{counts['open']:>10}"
                f"{counts['pending']:>10}{counts['future']:>9}{att_text:>9}{round(total, 2):>8}"
            )
            shown += 1
        if shown == 0:
            self.stdout.write(self.style.WARNING("Нет данных ни по одному студенту: начислять нечего."))
