from datetime import date
from io import BytesIO
from tempfile import NamedTemporaryFile

from django.test import TestCase
from openpyxl import Workbook

from apps.integrations.services.hik_xlsx_parser import parse_hik_export_rows, snapshot_payload_from_export


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
