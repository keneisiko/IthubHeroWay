from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.integrations.models import ExternalEvent, HikEvent
from apps.integrations.services.hik_attendance_processor import (
    parse_hik_event_time,
    process_unprocessed_hik_events,
)
from apps.integrations.services.hik_client import build_string_to_sign, sign_request

User = get_user_model()


class HikSignatureTests(TestCase):
    def test_signature_stable(self):
        sts = build_string_to_sign(
            method="POST",
            accept="application/json",
            content_type="application/json",
            app_key="ak",
            nonce="n1",
            timestamp_ms="1000",
            url_path="/artemis/api/demo",
            use_dash_ca_headers=True,
        )
        s1 = sign_request("sekret", sts)
        s2 = sign_request("sekret", sts)
        self.assertEqual(s1, s2)

    def test_build_string_contains_path(self):
        sts = build_string_to_sign(
            method="POST",
            accept="application/json",
            content_type="application/json",
            app_key="k",
            nonce="uuid",
            timestamp_ms="999",
            url_path="/artemis/foo?a=1",
            use_dash_ca_headers=True,
        )
        self.assertIn("/artemis/foo?a=1", sts)
        self.assertTrue(sts.startswith("POST"))

    def test_parse_time_ms_int(self):
        dt = parse_hik_event_time(1_730_000_000_123)
        self.assertIsNotNone(dt)


class HikProcessorTests(TestCase):
    def test_external_event_when_card_mapped(self):
        u = User.objects.create_user(
            username="hikstu",
            email="h@test.ru",
            password="x",
            callsign="hik_call",
            hik_card_code="CARD-X",
        )
        HikEvent.objects.create(
            event_id="HIK-E-1",
            student_code="CARD-X",
            event_time=timezone.now(),
            event_type="entry",
            door_name="Main",
            raw_data={"x": 1},
        )
        n, created, skipped = process_unprocessed_hik_events(limit=50)
        self.assertEqual(skipped, 0)
        self.assertGreaterEqual(n, 1)
        self.assertGreaterEqual(created, 1)
        ev = ExternalEvent.objects.get(source="hik", external_event_id="HIK-E-1")
        self.assertEqual(ev.payload.get("user_id"), u.pk)
