from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import generics, status, views
from rest_framework.response import Response

from apps.integrations.models import TelegramAccountLink
from apps.progress.models import RatingLog
from apps.quests.models import Quest, UserQuestProgress
from apps.quests.models import QuestRewardTransaction

from .models import Role, Squad, User
from .permissions import IsKnownRole
from .squads_serializers import (
    SquadCreateSerializer,
    SquadJoinSerializer,
    SquadListSerializer,
    SquadMemberPublicSerializer,
    SquadMemberSerializer,
    SquadMeWidgetSerializer,
)

SYNTHETIC_TELEGRAM_BASE = 5_100_000_000


def _ensure_telegram(user: User) -> None:
    if hasattr(user, "telegram_link") and user.telegram_link and user.telegram_link.is_active:
        return
    telegram_user_id = SYNTHETIC_TELEGRAM_BASE + int(user.pk)
    TelegramAccountLink.objects.update_or_create(
        user=user,
        defaults={
            "telegram_user_id": telegram_user_id,
            "telegram_chat_id": telegram_user_id,
            "telegram_username": "",
            "is_active": True,
        },
    )


def _agents_in_squad_filter():
    return Q(members__role="agent", members__telegram_link__is_active=True)


def _squad_stats_queryset():
    return Squad.objects.annotate(
        agents_count=Count("members", filter=_agents_in_squad_filter()),
        avg_rating=Avg("members__rating_current", filter=_agents_in_squad_filter()),
    )


class SquadListCreateView(views.APIView):
    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs):
        squads = _squad_stats_queryset().order_by("-avg_rating", "name")
        serializer = SquadListSerializer(squads, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        user: User = request.user
        if user.role != Role.AGENT:
            return Response({"detail": "Only agents can create squads."}, status=status.HTTP_403_FORBIDDEN)
        if user.squad_id:
            return Response({"detail": "You are already in a squad."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SquadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        name = data["name"].strip()
        base = slugify(name) or "squad"
        code = base
        counter = 1
        while Squad.objects.filter(code=code).exists():
            code = f"{base}-{counter}"
            counter += 1

        squad = Squad.objects.create(
            code=code,
            name=name,
            course=data.get("course"),
            capacity=data.get("capacity", 20),
        )
        _ensure_telegram(user)
        user.squad = squad
        user.save(update_fields=["squad"])
        cache.delete_pattern("leaderboard:squads:*")

        return Response(
            {
                "code": squad.code,
                "name": squad.name,
                "course": squad.course,
                "capacity": squad.capacity,
            },
            status=status.HTTP_201_CREATED,
        )


class SquadJoinView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, *args, **kwargs):
        user: User = request.user
        if user.squad_id:
            return Response({"detail": "You are already in a squad."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SquadJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"].strip().lower()

        squad = Squad.objects.filter(code__iexact=code).first()
        if not squad:
            return Response({"detail": "Squad not found."}, status=status.HTTP_404_NOT_FOUND)

        agents_count = User.objects.filter(
            squad=squad, role=Role.AGENT, telegram_link__is_active=True
        ).count()
        if squad.capacity is not None and agents_count >= squad.capacity:
            return Response({"detail": "Squad is full."}, status=status.HTTP_400_BAD_REQUEST)

        _ensure_telegram(user)
        user.squad = squad
        user.save(update_fields=["squad"])
        cache.delete_pattern("leaderboard:squads:*")

        return Response({"code": squad.code, "name": squad.name})


class SquadLeaveView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, *args, **kwargs):
        user: User = request.user
        if not user.squad_id:
            return Response({"detail": "You are not in a squad."}, status=status.HTTP_400_BAD_REQUEST)
        user.squad = None
        user.save(update_fields=["squad"])
        cache.delete_pattern("leaderboard:squads:*")
        return Response({"detail": "Left squad."})


class SquadMeView(views.APIView):
    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs):
        user: User = request.user
        if not user.squad_id:
            return Response(
                {
                    "my_squad": None,
                    "available_actions": ["join", "create"],
                    "team_bonus": None,
                    "actions": None,
                }
            )

        try:
            squad = Squad.objects.get(pk=user.squad_id)
        except Squad.DoesNotExist:
            return Response({"detail": "Squad not found."}, status=status.HTTP_404_NOT_FOUND)

        members_qs = (
            User.objects.filter(squad_id=squad.id, telegram_link__is_active=True)
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

        squads_stats = (
            Squad.objects.annotate(
                avg_rating=Avg(
                    "members__rating_current",
                    filter=Q(members__role="agent", members__telegram_link__is_active=True),
                )
            )
            .order_by("-avg_rating", "id")
        )
        squad_place = 1
        total_squads = squads_stats.count()
        for idx, s in enumerate(squads_stats, start=1):
            if s.id == squad.id:
                squad_place = idx
                break

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

        qs = User.objects.filter(squad=squad, telegram_link__is_active=True).select_related("track")

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(callsign__icontains=search)

        ordering = request.query_params.get("ordering", "rating")
        if ordering == "alpha":
            qs = qs.order_by("callsign", "id")
        elif ordering == "role":
            qs = qs.order_by("role", "-rating_current", "id")
        else:
            qs = qs.order_by("-rating_current", "id")

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

        squads = _squad_stats_queryset().order_by("-avg_rating", "id")[:limit]
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
