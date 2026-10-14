"""Какие статусы тем реально приходят из LXP.

Пункт 3.1 Положения исключает будущие КТ «по признаку их актуальности в LXP»,
но отдельного поля актуальности в выгрузке нет: актуальность выводится из
статуса темы. Набор маркеров (`POLOZHENIE_FUTURE_TOPIC_MARKERS`) нужно
сверять с живыми данными, иначе будущие КТ попадут в расчёт как несданные
и обвалят успеваемость всей группе.

    python manage.py probe_topic_statuses
    python manage.py probe_topic_statuses --date 2026-10-13
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.integrations.models import LXPSnapshot
from apps.integrations.services.lxp_snapshot_format import unwrap_category
from apps.progress.services.ct_status import is_topic_closed
from apps.progress.services.polozhenie_academic import is_future_topic


class Command(BaseCommand):
    help = "Печатает распределение статусов тем в снимке LXP и их трактовку Положением."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default="", help="Дата снимка (ГГГГ-ММ-ДД).")

    def handle(self, *args, **options):
        if options["date"]:
            try:
                target = date.fromisoformat(options["date"])
            except ValueError as exc:
                raise CommandError(f"Неверная дата: {options['date']}") from exc
            snap = LXPSnapshot.objects.filter(date=target).first()
        else:
            snap = LXPSnapshot.objects.order_by("-date").first()

        if snap is None:
            raise CommandError("Снимков LXP в базе нет.")

        block = (snap.data or {}).get("control_points")
        if not isinstance(block, dict) or not block.get("ok"):
            raise CommandError(f"В снимке {snap.date} нет годных данных по КТ.")

        data = unwrap_category(block)
        counter: Counter[str] = Counter()
        for row in data.values():
            if not isinstance(row, dict):
                continue
            for discipline in row.values():
                if not isinstance(discipline, dict):
                    continue
                topics = discipline.get("topics") or []
                if isinstance(topics, dict):
                    topics = list(topics.values())
                if not isinstance(topics, list):
                    continue
                for topic in topics:
                    if isinstance(topic, dict):
                        counter[str(topic.get("status") or topic.get("state") or "")] += 1

        total = sum(counter.values())
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Снимок {snap.date}: {len(data)} студентов, {total} тем\n"
            )
        )
        self.stdout.write(f"{'Статус':<34}{'Штук':>8}{'Доля':>8}  Трактовка по Положению")
        for status, count in counter.most_common():
            if is_future_topic(status):
                verdict = "будущая — в расчёт не входит"
            elif is_topic_closed(status):
                verdict = "актуальная, сдана — 100%"
            else:
                verdict = "актуальная, не сдана — 0%"
            share = f"{100.0 * count / total:.1f}%" if total else "—"
            shown = status or "(пусто)"
            self.stdout.write(f"{shown[:33]:<34}{count:>8}{share:>8}  {verdict}")

        self.stdout.write(
            "\nЕсли статус трактуется неверно, поправьте POLOZHENIE_FUTURE_TOPIC_MARKERS "
            "в hero_path/settings/polozhenie.py."
        )
