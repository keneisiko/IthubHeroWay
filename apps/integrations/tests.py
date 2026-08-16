import hashlib
import hmac
import json

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.integrations.models import ExternalEvent

SECRET = "test-webhook-secret"


def sign(payload: dict) -> str:
    body = json.dumps(payload).encode()
    return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


@override_settings(YOUGILE_WEBHOOK_SECRET=SECRET)
class YouGileWebhookTests(APITestCase):
    """События этого вебхука засчитывают квесты и начисляют награды,
    поэтому приём без подтверждения источника недопустим."""

    def test_signed_webhook_is_idempotent(self):
        url = reverse("yougile-webhook")
        payload = {"event_id": "evt-1", "type": "task.updated"}
        headers = {"HTTP_X_YOUGILE_SECRET": SECRET}

        r1 = self.client.post(url, payload, format="json", **headers)
        r2 = self.client.post(url, payload, format="json", **headers)

        self.assertEqual(r1.status_code, 202)
        self.assertEqual(r2.status_code, 202)
        self.assertEqual(
            ExternalEvent.objects.filter(source="yougile", external_event_id="evt-1").count(), 1
        )

    def test_hmac_signature_is_accepted(self):
        url = reverse("yougile-webhook")
        payload = {"event_id": "evt-hmac", "type": "task.closed"}
        body = json.dumps(payload)

        response = self.client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_X_YOUGILE_SIGNATURE=hmac.new(
                SECRET.encode(), body.encode(), hashlib.sha256
            ).hexdigest(),
        )

        self.assertEqual(response.status_code, 202)

    def test_unsigned_request_is_rejected(self):
        url = reverse("yougile-webhook")
        response = self.client.post(url, {"event_id": "evt-2"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ExternalEvent.objects.filter(external_event_id="evt-2").exists())

    def test_wrong_secret_is_rejected(self):
        url = reverse("yougile-webhook")
        response = self.client.post(
            url, {"event_id": "evt-3"}, format="json", HTTP_X_YOUGILE_SECRET="nope"
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(YOUGILE_WEBHOOK_SECRET="")
    def test_disabled_when_secret_not_configured(self):
        """Без настроенного секрета эндпоинт закрыт, а не открыт всем."""
        url = reverse("yougile-webhook")
        response = self.client.post(url, {"event_id": "evt-4"}, format="json")
        self.assertEqual(response.status_code, 403)
