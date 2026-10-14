"""Какие статусы тем приходят из LXP и что из них получается.

Пункт 3.1 Положения исключает будущие КТ «по признаку их актуальности в LXP»,
но отдельного поля актуальности в выгрузке нет: актуальность выводится из
статуса темы. Набор маркеров нужно сверять с живыми данными, иначе расчёт
успеваемости уезжает молча и сразу у всей группы.

Так и вышло при первом прогоне: в `NOT_PASSED_YET` есть подстрока `PASSED`,
и 91,6% тем читались как сданные. Поэтому команда печатает не только статусы,
но и распределение итоговой успеваемости — по нему ошибку видно сразу.

    python manage.py probe_topic_statuses
    python manage.py probe_topic_statuses --date 2026-10-13
    python manage.py probe_topic_statuses --students 10
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from apps.integrations.models import LXPSnapshot
from apps.integrations.services.lxp_snapshot_format import unwrap_category
from apps.progress.services.ct_status import is_topic_closed
from apps.progress.services.polozhenie_academic import (
    ct_percent_from_snapshot,
    is_future_topic,
    is_pending_topic,
)


class Command(BaseCommand):
    help = "Печатает статусы тем в снимке LXP, их трактовку и итоговую успеваемость."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default="", help="Дата снимка (ГГГГ-ММ-ДД).")
        parser.add_argument(
            "--students",
            type=int,
            default=0,
            help="Показать расчёт по N студентам поимённо (по идентификатору LXP).",
        )

    def handle(self, *args, **options):
        snap = self._snapshot(options["date"])
        data = self._control_points(snap)

        self._print_statuses(snap, data)
        self._print_percent_distribution(data)
        if options["students"]:
            self._print_students(data, options["students"])

        self.stdout.write(
            "\nЕсли статус трактуется неверно, поправьте POLOZHENIE_FUTURE_TOPIC_MARKERS "
            "или POLOZHENIE_PENDING_TOPIC_MARKERS в hero_path/settings/polozhenie.py."
        )

    def _snapshot(self, raw_date: str) -> LXPSnapshot:
        if raw_date:
            try:
                target = date.fromisoformat(raw_date)
            except ValueError as exc:
                raise CommandError(f"Неверная дата: {raw_date}") from exc
            snap = LXPSnapshot.objects.filter(date=target).first()
        else:
            snap = LXPSnapshot.objects.order_by("-date").first()
        if snap is None:
            raise CommandError("Снимков LXP в базе нет.")
        return snap

    def _control_points(self, snap: LXPSnapshot) -> dict:
        block = (snap.data or {}).get("control_points")
        if not isinstance(block, dict) or not block.get("ok"):
            raise CommandError(f"В снимке {snap.date} нет годных данных по КТ.")
        return unwrap_category(block)

    def _verdict(self, status: str) -> str:
        if is_future_topic(status):
            return "будущая — в расчёт не входит"
        if is_pending_topic(status):
            return "на проверке — в расчёт не входит"
        if is_topic_closed(status):
            return "актуальная, сдана — 100%"
        return "актуальная, не сдана — 0%"

    def _print_statuses(self, snap: LXPSnapshot, data: dict) -> None:
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
            self.style.MIGRATE_HEADING(f"Снимок {snap.date}: {len(data)} студентов, {total} тем\n")
        )
        self.stdout.write(f"{'Статус':<34}{'Штук':>8}{'Доля':>8}  Трактовка по Положению")
        for status, count in counter.most_common():
            share = f"{100.0 * count / total:.1f}%" if total else "—"
            self.stdout.write(
                f"{(status or '(пусто)')[:33]:<34}{count:>8}{share:>8}  {self._verdict(status)}"
            )

    def _percents(self, data: dict) -> list[tuple[str, Decimal, int, int]]:
        rows: list[tuple[str, Decimal, int, int]] = []
        for lxp_uid, row in data.items():
            if not isinstance(row, dict):
                continue
            percent, actual, passed = ct_percent_from_snapshot(row)
            if percent is None:
                continue
            rows.append((str(lxp_uid), percent, actual, passed))
        return rows

    def _print_percent_distribution(self, data: dict) -> None:
        rows = self._percents(data)
        self.stdout.write(self.style.MIGRATE_HEADING("\nУспеваемость (К) по студентам"))
        if not rows:
            self.stdout.write(
                self.style.ERROR(
                    "Ни у одного студента нет актуальных КТ — начисление за успеваемость "
                    "не произойдёт ни у кого. Проверьте маркеры: скорее всего, актуальные "
                    "темы попали в «будущие»."
                )
            )
            return

        percents = sorted(p for _, p, _, _ in rows)
        count = len(percents)
        median = percents[count // 2]
        ct_max = Decimal("17")
        self.stdout.write(
            f"  студентов с данными: {count} из {len(data)}\n"
            f"  минимум: {percents[0]}%   медиана: {median}%   максимум: {percents[-1]}%\n"
            f"  медианное начисление за успеваемость: {round(ct_max * median / 100, 2)} из {ct_max}"
        )

        buckets = [(0, 25), (25, 50), (50, 75), (75, 100), (100, 101)]
        self.stdout.write("\n  Распределение:")
        for low, high in buckets:
            hit = sum(1 for p in percents if low <= p < high)
            label = "100%" if low == 100 else f"{low}–{high}%"
            bar = "#" * min(40, round(40 * hit / count))
            self.stdout.write(f"    {label:>9}  {hit:>5}  {bar}")

        if percents[-1] == 100 and sum(1 for p in percents if p == 100) > count * 0.8:
            self.stdout.write(
                self.style.ERROR(
                    "\n  У больше чем 80% студентов успеваемость 100%. Так не бывает: "
                    "скорее всего несданные темы читаются как сданные."
                )
            )

    def _print_students(self, data: dict, limit: int) -> None:
        rows = sorted(self._percents(data), key=lambda row: row[1])
        self.stdout.write(self.style.MIGRATE_HEADING(f"\nПервые {limit} студентов по возрастанию К"))
        self.stdout.write(f"{'LXP id':<40}{'К, %':>8}{'сдано':>8}{'актуальных':>12}")
        for lxp_uid, percent, actual, passed in rows[:limit]:
            self.stdout.write(f"{lxp_uid[:39]:<40}{percent:>8}{passed:>8}{actual:>12}")
