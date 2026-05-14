from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework import generics, views
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsKnownRole
from .models import RatingLog
from .serializers import LeaderboardAgentSerializer, RatingLogSerializer, RatingMeSerializer


class RatingMeView(views.APIView):
    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs):
        return Response(RatingMeSerializer(request.user).data)


class RatingHistoryView(generics.ListAPIView):
    permission_classes = [IsKnownRole]
    serializer_class = RatingLogSerializer

    def get_queryset(self):
        queryset = RatingLog.objects.filter(user=self.request.user).order_by("-created_at")
        period = self.request.query_params.get("period")
        if period == "week":
            queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=7))
        elif period == "month":
            queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=30))
        return queryset


class AgentLeaderboardView(generics.ListAPIView):
    permission_classes = [IsKnownRole]
    serializer_class = LeaderboardAgentSerializer

    def get_queryset(self):
        queryset = User.objects.filter(telegram_link__is_active=True).order_by("-rating_current", "id")
        track = self.request.query_params.get("track")
        course = self.request.query_params.get("course")
        if track:
            queryset = queryset.filter(track__code=track)
        if course:
            queryset = queryset.filter(squad__course=course)
        return queryset

    def list(self, request, *args, **kwargs):
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        track = request.query_params.get("track", "")
        course = request.query_params.get("course", "")
        cache_key = f"leaderboard:agents:p{page}:s{page_size}:t{track}:c{course}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        queryset = self.filter_queryset(self.get_queryset())
        page_obj = self.paginate_queryset(queryset)
        data = self.get_serializer(page_obj, many=True).data if page_obj is not None else self.get_serializer(queryset, many=True).data
        if page_obj is not None:
            response = self.get_paginated_response(data)
            payload = response.data
        else:
            payload = data
        ttl = getattr(settings, "LEADERBOARD_CACHE_TTL", 300)
        cache.set(cache_key, payload, ttl)
        return Response(payload)

