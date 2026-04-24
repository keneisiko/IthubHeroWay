from django.urls import reverse
from rest_framework.test import APITestCase

from apps.integrations.models import ExternalEvent


class IntegrationsIdempotencyTests(APITestCase):
    def test_yougile_webhook_is_idempotent(self):
        url = reverse("yougile-webhook")
        payload = {"event_id": "evt-1", "type": "task.updated"}
        r1 = self.client.post(url, payload, format="json")
        r2 = self.client.post(url, payload, format="json")
        self.assertEqual(r1.status_code, 202)
        self.assertEqual(r2.status_code, 202)
        self.assertEqual(ExternalEvent.objects.filter(source="yougile", external_event_id="evt-1").count(), 1)

