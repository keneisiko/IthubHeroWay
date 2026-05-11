from rest_framework import generics, views
from rest_framework.response import Response
from django.core.cache import cache

from .models import User
from .serializers import MeProfileSerializer, PublicProfileSerializer
from .permissions import IsKnownRole
from apps.quests.models import Quest, UserQuestProgress


class MeProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = MeProfileSerializer
    permission_classes = [IsKnownRole]

    def get_object(self) -> User:
        return self.request.user

    def perform_update(self, serializer):
        user = serializer.save()
        cache.delete_pattern(f"profile:{user.username}*")


class PublicProfileView(generics.RetrieveAPIView):
    permission_classes = [IsKnownRole]
    serializer_class = PublicProfileSerializer
    lookup_field = "username"
    queryset = User.objects.select_related("track", "squad")

    def retrieve(self, request, *args, **kwargs):
        username = kwargs.get("username")
        cache_key = f"profile:{username}:viewer:{request.user.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        response = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, 60)
        return response


class DashboardView(views.APIView):
    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs) -> Response:
        user = request.user
        current_quest = Quest.objects.filter(is_active=True).order_by("id").first()
        current_quest_payload = None
        if current_quest:
            progress = UserQuestProgress.objects.filter(user=user, quest=current_quest).first()
            current_quest_payload = {
                "code": current_quest.code,
                "title": current_quest.title,
                "quest_type": current_quest.quest_type,
                "reward_coins": current_quest.reward_coins,
                "reward_rating_delta": current_quest.reward_rating_delta,
                "progress_value": progress.progress_value if progress else 0,
                "is_completed": progress.is_completed if progress else False,
            }

        data = {
            "user": MeProfileSerializer(user).data,
            "current_quest": current_quest_payload,
            "strike": None,
            "recent_badges": [],
            "feed": [],
        }
        return Response(data)

