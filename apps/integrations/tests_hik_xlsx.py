from datetime import date
from tempfile import NamedTemporaryFile

from django.test import TestCase
from openpyxl import Workbook

from apps.integrations.services.hik_xlsx_parser import (
    HikExportFormatError,
    parse_hik_export_rows,
    snapshot_payload_from_export,
)


class HikXlsxParserTests(TestCase):
    def _write_xlsx(self, rows: list[list]) -> str:
        wb = Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        tmp = NamedTemporaryFile(suffix=".xlsx", delete=False)
        wb.save(tmp.name)
        wb.close()
        return tmp.name

    def test_parse_russian_headers(self):
        path = self._write_xlsx(
            [
                ["ФИО", "Номер карты", "Дата и время", "Турникет", "Статус"],
                ["Иванов", "CARD-100", "2026-05-30 08:55:00", "Вход 1", "access"],
                ["Петров", "CARD-200", "2026-05-30 09:20:00", "Вход 1", "late"],
            ]
        )
        events = parse_hik_export_rows(path, fallback_date=date(2026, 5, 30))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["personCode"], "CARD-100")
        self.assertIn("2026-05-30", events[0]["eventTime"])
        self.assertEqual(events[1]["doorName"], "Вход 1")

    def test_event_id_is_stable_when_export_grows(self):
        """Ключевой сценарий прода: выгрузка «за сегодня» скачивается каждый час.

        Файл растёт, а портал отдаёт новые записи сверху. Идентификаторы уже
        импортированных событий обязаны остаться прежними, иначе события
        задваиваются вместе со штрафами рейтинга.
        """
        header = ["Номер карты", "Дата и время", "Турникет"]
        morning = ["CARD-100", "2026-05-30 08:55:00", "Вход 1"]
        midday = ["CARD-200", "2026-05-30 12:10:00", "Вход 1"]

        first_export = self._write_xlsx([header, morning])
        # Новая запись добавлена сверху — позиции строк сдвинулись.
        second_export = self._write_xlsx([header, midday, morning])

        first_ids = {e["eventId"] for e in parse_hik_export_rows(first_export)}
        second_ids = {e["eventId"] for e in parse_hik_export_rows(second_export)}

        self.assertTrue(first_ids.issubset(second_ids))
        self.assertEqual(len(second_ids), 2)

    def test_identical_passes_get_distinct_ids(self):
        """Два реальных прохода с одинаковыми полями не должны схлопываться."""
        path = self._write_xlsx(
            [
                ["Номер карты", "Дата и время", "Турникет"],
                ["CARD-100", "2026-05-30 08:55:00", "Вход 1"],
                ["CARD-100", "2026-05-30 08:55:00", "Вход 1"],
            ]
        )
        events = parse_hik_export_rows(path)
        self.assertEqual(len({e["eventId"] for e in events}), 2)

    def test_unknown_headers_raise_instead_of_silent_empty(self):
        """Не тот отчёт — это ошибка, а не «сегодня никто не приходил»."""
        path = self._write_xlsx(
            [
                ["Колонка А", "Колонка Б"],
                ["значение", "другое"],
            ]
        )
        with self.assertRaises(HikExportFormatError):
            parse_hik_export_rows(path)

    def test_report_title_above_headers_is_skipped(self):
        """Перед таблицей часто идёт шапка отчёта — она не должна стать заголовками."""
        path = self._write_xlsx(
            [
                ["Отчёт: Записи прохода"],
                ["Период: 30.05.2026 - 30.05.2026"],
                ["Номер карты", "Дата и время", "Турникет"],
                ["CARD-777", "30.05.2026 08:45:00", "Вход 1"],
            ]
        )
        events = parse_hik_export_rows(path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["personCode"], "CARD-777")

    def test_date_only_value_is_not_treated_as_midnight(self):
        """Дата без времени раньше означала «пришёл в 00:00», то есть всегда вовремя."""
        path = self._write_xlsx(
            [
                ["Номер карты", "Дата и время", "Турникет"],
                ["CARD-100", "2026-05-30", "Вход 1"],
            ]
        )
        with self.assertRaises(HikExportFormatError):
            parse_hik_export_rows(path)

    def test_device_id_column_is_not_taken_as_card_code(self):
        """Подстрочный матчинг раньше принимал «Device ID» за колонку кода карты."""
        path = self._write_xlsx(
            [
                ["Device ID", "Person No", "Event Time", "Door Name"],
                ["DEV-9", "42", "2026-05-30 08:40:00", "Main"],
            ]
        )
        events = parse_hik_export_rows(path)
        self.assertEqual(events[0]["personCode"], "42")

    def test_snapshot_payload(self):
        path = self._write_xlsx(
            [
                ["Person No", "Event Time", "Door Name"],
                ["42", "2026-05-30 08:40:00", "Main"],
            ]
        )
        payload = snapshot_payload_from_export(path, date(2026, 5, 30))
        self.assertEqual(payload["meta"]["source"], "browser_xlsx")
        self.assertEqual(len(payload["events"]), 1)
        self.assertEqual(payload["events"][0]["personCode"], "42")
