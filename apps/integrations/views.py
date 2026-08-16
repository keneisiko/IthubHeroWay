import hashlib
import hmac
import logging

from django.conf import settings
from rest_framework import permissions, status, views
from rest_framework.response import Response

from .models import ExternalEvent

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "HTTP_X_YOUGILE_SIGNATURE"
SECRET_HEADER = "HTTP_X_YOUGILE_SECRET"


def _signature_valid(request) -> bool:
    """Проверить подпись или общий секрет вебхука.

    Раньше эндпоинт был полностью открыт, а созданные им события напрямую
    засчитывают квесты и начисляют монеты с рейтингом: постучавшись сюда,
    посторонний мог накрутить награды себе или другому студенту.
    """
    secret = (getattr(settings, "YOUGILE_WEBHOOK_SECRET", "") or "").strip()
    if not secret:
        # Без настроенного секрета приём выключен: открытый эндпоинт,
        # влияющий на рейтинг, — не то, что должно работать «по умолчанию».
        return False

    provided_secret = request.META.get(SECRET_HEADER, "")
    if provided_secret and hmac.compare_digest(provided_secret, secret):
        return True

    signature = request.META.get(SIGNATURE_HEADER, "")
    if not signature:
        return False
    expected = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.strip().lower(), expected)


class YouGileWebhookView(views.APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "webhook"

    def post(self, request, *args, **kwargs):
        if not _signature_valid(request):
            logger.warning("YouGile webhook: отклонён запрос без валидной подписи")
            return Response(
                {"detail": "Invalid or missing webhook signature."},
                status=status.HTTP_403_FORBIDDEN,
            )

        external_event_id = str(request.data.get("event_id") or request.data.get("id") or "")
        if not external_event_id:
            return Response({"detail": "event_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        _, created = ExternalEvent.objects.get_or_create(
            source="yougile",
            external_event_id=external_event_id,
            defaults={"payload": request.data},
        )
        return Response({"status": "accepted", "created": created}, status=status.HTTP_202_ACCEPTED)
