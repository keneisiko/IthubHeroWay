from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.response import Response

from apps.progress.models import RatingLog
from apps.quests.models import Quest, UserQuestProgress
from apps.quests.models import QuestRewardTransaction

from .models import Squad, User
from .permissions import IsKnownRole
from .squads_serializers import SquadMemberPublicSerializer, SquadMemberSerializer, SquadMeWidgetSerializer


class SquadMeView(views.APIView):
    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs):
        user: User = request.user
        if not user.squad_id:
            return Response({"detail": "User has no squad."}, status=status.HTTP_404_NOT_FOUND)

        squad = Squad.objects.get(pk=user.squad_id)
        members_qs = (
            User.objects.filter(squad_id=squad.id)
            .select_related("track")
        )

        agents_qs = members_qs.filter(role="agent")
        agents_count = agents_qs.count()

        rating_avg = agents_qs.aggregate(v=Avg("rating_current"))["v"] or 0

        week_ago = timezone.now() - timedelta(days=7)
        delta_week = (
            RatingLog.objects.filter(user__in=agents_qs, created_at__gte=week_ago).aggregate(v=Sum("delta"))["v"]
            or 0
        )

        # Squad place in leaderboard by average rating.
        squads_stats = (
            Squad.objects.annotate(avg_rating=Avg("members__rating_current", filter=Q(members__role="agent")))
            .order_by("-avg_rating", "id")
        )
        squad_place = 1
        total_squads = squads_stats.count()
        for idx, s in enumerate(squads_stats, start=1):
            if s.id == squad.id:
                squad_place = idx
                break

        # Weekly quest bonus progress (active weekly quest).
        now = timezone.now()
        weekly_quest = (
            Quest.objects.filter(is_active=True, quest_type="weekly")
            .filter(Q(start_at__isnull=True) | Q(start_at__lte=now))
            .order_by("id")
            .first()
        )
        weekly_completed = 0
        if weekly_quest and agents_count:
            weekly_completed = UserQuestProgress.objects.filter(
                quest=weekly_quest, is_completed=True, user__in=agents_qs
            ).count()
        weekly_percent = (weekly_completed / agents_count) if agents_count else 0
        weekly_bonus_active = weekly_percent >= 0.8
        weekly_remaining = max(0, int(0.8 * agents_count + 0.999) - weekly_completed) if agents_count else 0

        # Monthly coins earned by squad (MVP: quest reward coins only).
        month_ago = timezone.now() - timedelta(days=30)
        month_coins = (
            QuestRewardTransaction.objects.filter(user__in=agents_qs, granted_at__gte=month_ago).aggregate(
                v=Sum("coins_delta")
            )["v"]
            or 0
        )

        data = {
            "my_squad": {
                **SquadMeWidgetSerializer(squad).data,
                "agents_count": agents_count,
                "squad_rating_avg": round(float(rating_avg), 2),
                "delta_week": int(delta_week),
                "place": squad_place,
                "total_squads": total_squads,
            },
            "team_bonus": {
                "weekly_quest": {
                    "code": weekly_quest.code,
                    "title": weekly_quest.title,
                }
                if weekly_quest
                else None,
                "completed": weekly_completed,
                "total": agents_count,
                "percent": round(weekly_percent * 100, 2),
                "bonus_threshold_percent": 80,
                "bonus_reward_coins": 5,
                "status": "active" if weekly_bonus_active else "not_ready",
                "remaining_to_threshold": weekly_remaining,
            },
            "actions": {
                "share_url": f"/squads/{squad.code}",
                "month_coins": int(month_coins),
            },
        }
        return Response(data)


class SquadMembersView(generics.ListAPIView):
    permission_classes = [IsKnownRole]

    def get(self, request, code: str, *args, **kwargs):
        user: User = request.user
        squad = generics.get_object_or_404(Squad, code=code)

        qs = User.objects.filter(squad=squad).select_related("track")

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(callsign__icontains=search)

        ordering = request.query_params.get("ordering", "rating")
        if ordering == "alpha":
            qs = qs.order_by("callsign", "id")
        elif ordering == "role":
            qs = qs.order_by("role", "-rating_current", "id")
        else:  # rating
            qs = qs.order_by("-rating_current", "id")

        # Exact ratings are visible only for same squad members (per TЗ).
        if user.squad_id == squad.id:
            serializer = SquadMemberSerializer(qs, many=True)
        else:
            serializer = SquadMemberPublicSerializer(qs, many=True)

        return Response(serializer.data)


class SquadLeaderboardView(views.APIView):
    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs):
        limit = int(request.query_params.get("limit", 20))
        cache_key = f"leaderboard:squads:{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        squads = (
            Squad.objects.annotate(
                agents_count=Count("members", filter=Q(members__role="agent")),
                avg_rating=Avg("members__rating_current", filter=Q(members__role="agent")),
            )
            .order_by("-avg_rating", "id")[:limit]
        )
        data = [
            {
                "code": s.code,
                "name": s.name,
                "course": s.course,
                "agents_count": s.agents_count or 0,
                "avg_rating": round(float(s.avg_rating or 0), 2),
            }
            for s in squads
        ]
        ttl = getattr(settings, "LEADERBOARD_CACHE_TTL", 300)
        cache.set(cache_key, data, ttl)
        return Response(data)

