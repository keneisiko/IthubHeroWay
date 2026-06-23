"""
Ручной забор проходов Hik-Connect (аналог pull_lxp_performance).

Сохраняет JSON в HikSnapshot, импортирует в HikEvent и выпускает ExternalEvent
(опоздания, штрафы, квесты daily-hik-*).
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.integrations.services.hik_snapshot_service import (
    apply_hik_snapshot,
    build_synthetic_snapshot,
    export_snapshot_template,
    load_snapshot_from_file,
    save_hik_snapshot,
)


class Command(BaseCommand):
    help = (
        "Импорт проходов Hik в HikSnapshot (файл или синтетика) и обработка "
        "→ HikEvent → ExternalEvent. Без API HikCentral."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="snapshot_date",
            type=str,
            default="",
            help="Дата снимка ISO (YYYY-MM-DD). По умолчанию — сегодня.",
        )
        parser.add_argument(
            "--yesterday",
            action="store_true",
            help="Снимок за вчера.",
        )
        parser.add_argument(
            "--from-file",
            type=str,
            default="",
            help="Путь к JSON (массив events или объект с полем events).",
        )
        parser.add_argument(
            "--synthetic",
            action="store_true",
            help="Сгенерировать демо-проходы для агентов с hik_card_code.",
        )
        parser.add_argument(
            "--assign-hik-cards",
            action="store_true",
            help="С --synthetic: проставить hik_card_code агентам без карты (HIK-DEMO-<id>).",
        )
        parser.add_argument(
            "--skip-process",
            action="store_true",
            help="Только сохранить снимок и HikEvent, без ExternalEvent/штрафов.",
        )
        parser.add_argument(
            "--process-only",
            action="store_true",
            help="Не загружать JSON — обработать уже сохранённый HikSnapshot за дату.",
        )
        parser.add_argument(
            "--export-template",
            action="store_true",
            help="Вывести пример JSON и выйти.",
        )
        parser.add_argument(
            "--verify-quests",
            action="store_true",
            help="После обработки запустить verify_auto_quests (daily).",
        )

    def handle(self, *args, **opts):
        if opts["export_template"]:
            self.stdout.write(json.dumps(export_snapshot_template(), ensure_ascii=False, indent=2))
            return

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

        self.stdout.write(self.style.NOTICE(f"Дата снимка Hik: {target_date.isoformat()}"))

        if opts["process_only"]:
            result = apply_hik_snapshot(target_date, skip_process=opts["skip_process"])
            self._print_result(result)
            self._maybe_verify_quests(opts, target_date)
            return

        if opts["from_file"]:
            path = opts["from_file"].strip()
            try:
                raw = load_snapshot_from_file(path)
            except OSError as e:
                raise CommandError(f"Не удалось прочитать файл: {e}") from e
            except json.JSONDecodeError as e:
                raise CommandError(f"Невалидный JSON: {e}") from e
            snap = save_hik_snapshot(target_date, raw)
            self.stdout.write(self.style.SUCCESS(f"HikSnapshot из файла сохранён ({path})."))
        elif opts["synthetic"]:
            data = build_synthetic_snapshot(
                target_date,
                assign_missing_cards=opts["assign_hik_cards"],
            )
            snap = save_hik_snapshot(target_date, data)
            meta = (snap.data or {}).get("meta") or {}
            self.stdout.write(
                self.style.SUCCESS(
                    f"Синтетический HikSnapshot: events={meta.get('events_count', 0)}"
                )
            )
        else:
            raise CommandError(
                "Укажите источник: --from-file путь.json, --synthetic или --process-only"
            )

        result = apply_hik_snapshot(target_date, skip_process=opts["skip_process"])
        self._print_result(result)
        self._maybe_verify_quests(opts, target_date)

    def _print_result(self, result: dict) -> None:
        if result.get("error") == "no_snapshot":
            raise CommandError(f"Нет HikSnapshot за {result.get('date')}")

        if result.get("process_skipped"):
            self.stdout.write(
                self.style.WARNING(
                    f"Импорт: seen={result.get('import_seen')} new={result.get('import_inserted')} "
                    f"(обработка пропущена --skip-process)"
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Hik: import seen={result.get('import_seen')} new={result.get('import_inserted')} | "
                f"process={result.get('process_seen')} external={result.get('external_created')} "
                f"no_user={result.get('skipped_no_user')}"
            )
        )

    def _maybe_verify_quests(self, opts, target_date: date) -> None:
        if not opts["verify_quests"] or opts["skip_process"]:
            return
        from apps.quests.services.quest_verification import verify_all_auto_quests
        from apps.quests.models import QuestType

        stats = verify_all_auto_quests(target_date, quest_types=[QuestType.DAILY])
        self.stdout.write(self.style.SUCCESS(f"Квесты (daily): {stats}"))
