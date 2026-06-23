from rest_framework import views
from rest_framework.response import Response

from apps.progress.services.pillar_labels import characteristics_payload

from .permissions import IsKnownRole


class MeCharacteristicsView(views.APIView):
    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs):
        return Response(characteristics_payload(request.user))
