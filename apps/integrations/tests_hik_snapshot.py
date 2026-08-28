from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role
from apps.integrations.models import ExternalEvent
from apps.integrations.services.hik_snapshot_service import (
    apply_hik_snapshot,
    build_synthetic_snapshot,
    import_snapshot_to_hik_events,
    load_snapshot_from_file,
    normalize_snapshot_payload,
    save_hik_snapshot,
)
from apps.schedule.models import Schedule


class HikSnapshotServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="hik_agent",
            password="x",
            callsign="hik_agent",
            role=Role.AGENT,
            hik_card_code="CARD-TEST-1",
        )
        self.squad = __import__("apps.accounts.models", fromlist=["Squad"]).Squad.objects.create(
            code="S-HIK", name="Hik Squad", course=2
        )
        self.user.squad = self.squad
        self.user.save(update_fields=["squad"])
        Schedule.objects.create(
            squad=self.squad,
            day_of_week=timezone.localdate().weekday(),
            start_time=time(9, 0),
            end_time=time(10, 30),
            discipline="Demo",
            is_active=True,
        )

    def test_normalize_list_payload(self):
        today = timezone.localdate()
        raw = [{"eventId": "e1", "personCode": "CARD-TEST-1", "eventTime": "2026-01-01T08:00:00"}]
        data = normalize_snapshot_payload(raw, today)
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["meta"]["format"], "list")

    def test_synthetic_import_and_process(self):
        today = timezone.localdate()
        data = build_synthetic_snapshot(today)
        save_hik_snapshot(today, data)
        result = apply_hik_snapshot(today, skip_process=False)
        self.assertGreaterEqual(result.get("import_inserted", 0), 1)
        self.assertGreaterEqual(result.get("external_created", 0), 1)
        self.assertTrue(
            ExternalEvent.objects.filter(source="hik", payload__user_id=self.user.pk).exists()
        )

    def test_import_from_example_file(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "docs" / "examples" / "hik_snapshot.example.json"
        if not path.exists():
            self.skipTest("example file missing")
        raw = load_snapshot_from_file(path)
        today = date.fromisoformat(raw["date"]) if raw.get("date") else timezone.localdate()
        self.user.hik_card_code = "CARD-12345"
        self.user.save(update_fields=["hik_card_code"])
        snap = save_hik_snapshot(today, raw)
        seen, inserted, _ = import_snapshot_to_hik_events(snap)
        self.assertGreaterEqual(seen, 1)
