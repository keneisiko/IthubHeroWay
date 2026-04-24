from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, status, views
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsKnownRole
from .models import Duel, DuelStatus, Mentorship, Respect
from .serializers import (
    DuelCreateSerializer,
    DuelSerializer,
    MentorshipCreateSerializer,
    MentorshipSerializer,
    RespectCreateSerializer,
    RespectSerializer,
)


class RespectCreateView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, *args, **kwargs):
        serializer = RespectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        to_user = generics.get_object_or_404(User, username=serializer.validated_data["to_username"])
        if to_user.pk == request.user.pk:
            return Response({"detail": "Cannot send respect to yourself."}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        # 1 respect per week per sender.
        if Respect.objects.filter(from_user=request.user, created_at__gte=now - timedelta(days=7)).exists():
            return Response({"detail": "Weekly respect limit reached."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        # Can't send to the same recipient in two consecutive weeks.
        if Respect.objects.filter(
            from_user=request.user,
            to_user=to_user,
            created_at__gte=now - timedelta(days=14),
        ).exists():
            return Response(
                {"detail": "You can respect this user again in two weeks."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        respect = Respect.objects.create(
            from_user=request.user,
            to_user=to_user,
            message=serializer.validated_data.get("message", ""),
        )
        return Response(RespectSerializer(respect).data, status=status.HTTP_201_CREATED)


class DuelCreateView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, *args, **kwargs):
        serializer = DuelCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        opponent = generics.get_object_or_404(User, username=serializer.validated_data["opponent_username"])
        if opponent.pk == request.user.pk:
            return Response({"detail": "Cannot duel yourself."}, status=status.HTTP_400_BAD_REQUEST)
        # One active duel at a time.
        active_q = Q(status=DuelStatus.PENDING) | (Q(status=DuelStatus.ACCEPTED) & Q(resolved_at__isnull=True))
        if Duel.objects.filter(active_q).filter(Q(challenger=request.user) | Q(opponent=request.user)).exists():
            return Response({"detail": "You already have an active duel."}, status=status.HTTP_400_BAD_REQUEST)
        if Duel.objects.filter(active_q).filter(Q(challenger=opponent) | Q(opponent=opponent)).exists():
            return Response({"detail": "Opponent already has an active duel."}, status=status.HTTP_400_BAD_REQUEST)
        if abs(request.user.rating_current - opponent.rating_current) > 150:
            return Response({"detail": "Rating difference must be 150 or less."}, status=status.HTTP_400_BAD_REQUEST)
        duel = Duel.objects.create(challenger=request.user, opponent=opponent, status=DuelStatus.PENDING)
        return Response(DuelSerializer(duel).data, status=status.HTTP_201_CREATED)


class DuelAcceptView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, duel_id: int, *args, **kwargs):
        duel = generics.get_object_or_404(Duel, id=duel_id, opponent=request.user)
        duel.status = DuelStatus.ACCEPTED
        duel.resolved_at = timezone.now()
        duel.save(update_fields=["status", "resolved_at"])
        return Response(DuelSerializer(duel).data, status=status.HTTP_200_OK)


class DuelRejectView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, duel_id: int, *args, **kwargs):
        duel = generics.get_object_or_404(Duel, id=duel_id, opponent=request.user)
        duel.status = DuelStatus.REJECTED
        duel.resolved_at = timezone.now()
        duel.save(update_fields=["status", "resolved_at"])
        return Response(DuelSerializer(duel).data, status=status.HTTP_200_OK)


class MentorshipCreateView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, *args, **kwargs):
        serializer = MentorshipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mentee = generics.get_object_or_404(User, username=serializer.validated_data["mentee_username"])
        mentorship, _ = Mentorship.objects.get_or_create(mentor=request.user, mentee=mentee)
        return Response(MentorshipSerializer(mentorship).data, status=status.HTTP_201_CREATED)

