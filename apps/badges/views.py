from rest_framework import generics, status, views
from rest_framework.response import Response

from apps.accounts.permissions import IsKnownRole

from .models import Badge, UserBadge
from .serializers import BadgeSerializer, UserBadgeSerializer
from .services import award_badges_for_user


class BadgeListView(generics.ListAPIView):
    permission_classes = [IsKnownRole]
    serializer_class = BadgeSerializer
    queryset = Badge.objects.filter(is_active=True).order_by("id")


class MyBadgeListView(generics.ListAPIView):
    permission_classes = [IsKnownRole]
    serializer_class = UserBadgeSerializer

    def get_queryset(self):
        return UserBadge.objects.filter(user=self.request.user).select_related("badge").order_by("-acquired_at")


class BadgePinView(views.APIView):
    """Закрепить значок в профиле или снять закрепление.

    Раньше был только POST, который выставлял `is_pinned = True`: открепить
    значок было нельзя ни через API, ни из интерфейса — закрепив три,
    студент оставался с ними навсегда.
    """

    permission_classes = [IsKnownRole]

    def _get_badge(self, request, code: str) -> UserBadge:
        return generics.get_object_or_404(
            UserBadge.objects.select_related("badge"), user=request.user, badge__code=code
        )

    def post(self, request, code: str) -> Response:
        user_badge = self._get_badge(request, code)
        user_badge.is_pinned = True
        user_badge.save(update_fields=["is_pinned"])
        return Response(UserBadgeSerializer(user_badge).data, status=status.HTTP_200_OK)

    def delete(self, request, code: str) -> Response:
        user_badge = self._get_badge(request, code)
        user_badge.is_pinned = False
        user_badge.save(update_fields=["is_pinned"])
        return Response(UserBadgeSerializer(user_badge).data, status=status.HTTP_200_OK)


class BadgeAwardCheckView(views.APIView):
    permission_classes = [IsKnownRole]
    # Проверка перебирает все активные значки с запросом на каждый,
    # поэтому без ограничения частоты эндпоинт работает генератором нагрузки.
    throttle_scope = "heavy"

    def post(self, request, *args, **kwargs) -> Response:
        awarded = award_badges_for_user(request.user)
        return Response({"awarded_count": len(awarded)}, status=status.HTTP_200_OK)

