from rest_framework import permissions, status, views
from rest_framework.response import Response

from .models import ExternalEvent


class YouGileWebhookView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        external_event_id = str(request.data.get("event_id") or request.data.get("id") or "")
        if not external_event_id:
            return Response({"detail": "event_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        _, created = ExternalEvent.objects.get_or_create(
            source="yougile",
            external_event_id=external_event_id,
            defaults={"payload": request.data},
        )
        return Response({"status": "accepted", "created": created}, status=status.HTTP_202_ACCEPTED)

