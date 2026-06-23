from rest_framework import generics, views
from rest_framework.response import Response
from django.core.cache import cache

from .models import User
from .serializers import MeProfileSerializer, PublicProfileSerializer
from .permissions import IsKnownRole
from .characteristics_views import MeCharacteristicsView
from apps.quests.models import Quest, UserQuestProgress
from apps.progress.models import UserStrike
from apps.progress.services.late_penalties import late_streak_bonus_for_days
from apps.progress.services.pillar_labels import skills_percent_by_label
from apps.progress.services.rating_zones import rating_progress


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


def _strike_payload(user: User) -> dict:
    strike, _ = UserStrike.objects.get_or_create(user=user)
    late = strike.late_strike
    if late < 7:
        next_milestone = 7
        prev_milestone = 0
        bonus_at_next = late_streak_bonus_for_days(7)
    elif late < 14:
        next_milestone = 14
        prev_milestone = 7
        bonus_at_next = late_streak_bonus_for_days(14)
    elif late < 21:
        next_milestone = 21
        prev_milestone = 14
        bonus_at_next = late_streak_bonus_for_days(21)
    else:
        next_milestone = 21
        prev_milestone = 21
        bonus_at_next = late_streak_bonus_for_days(21)

    span = max(1, next_milestone - prev_milestone)
    segment_progress = min(100.0, round((late - prev_milestone) / span * 100, 1))

    return {
        "attendance_strike": strike.attendance_strike,
        "late_strike": late,
        "next_late_milestone": next_milestone,
        "prev_late_milestone": prev_milestone,
        "bonus_at_next_milestone": bonus_at_next,
        "bonus_at_7": late_streak_bonus_for_days(7),
        "bonus_at_14": late_streak_bonus_for_days(14),
        "bonus_at_21": late_streak_bonus_for_days(21),
        "segment_progress_percent": segment_progress,
        "overall_progress_percent": min(100.0, round(late / 21 * 100, 1)),
    }


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
            from apps.quests.services.quest_conditions import is_auto_verified, is_manual_complete_allowed

            current_quest_payload["auto_verify"] = is_auto_verified(current_quest)
            current_quest_payload["manual_complete_allowed"] = is_manual_complete_allowed(current_quest)
            if progress and isinstance(progress.proof_payload, dict):
                current_quest_payload["verification_message"] = progress.proof_payload.get("message") or ""

        skills, skills_peak = skills_percent_by_label(user)
        user_data = MeProfileSerializer(user).data
        user_data["skills"] = skills
        user_data["skills_peak"] = skills_peak

        data = {
            "user": user_data,
            "current_quest": current_quest_payload,
            "strike": _strike_payload(user),
            "rating_progress": rating_progress(user.rating_current),
            "recent_badges": [],
            "feed": [],
        }
        return Response(data)
