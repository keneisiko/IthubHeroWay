from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
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
        limits = getattr(settings, "RATING_LIMITS", {})
        respect_weekly = int(limits.get("RESPECT_WEEKLY_LIMIT", 1))
        same_user_cooldown_days = int(limits.get("RESPECT_SAME_USER_COOLDOWN", 14))
        now = timezone.now()
        # Проверка лимитов и создание респекта — одна транзакция с блокировкой
        # строки отправителя: раньше count()/exists() и create() шли врозь,
        # и два одновременных запроса от одного пользователя оба видели лимит
        # невыбранным, после чего оба создавали респект. Блокируется отправитель,
        # потому что лимит считается именно по нему.
        with transaction.atomic():
            User.objects.select_for_update().filter(pk=request.user.pk).first()
            if respect_weekly > 0 and Respect.objects.filter(
                from_user=request.user,
                created_at__gte=now - timedelta(days=7),
            ).count() >= respect_weekly:
                return Response(
                    {"detail": "Weekly respect limit reached."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            if Respect.objects.filter(
                from_user=request.user,
                to_user=to_user,
                created_at__gte=now - timedelta(days=same_user_cooldown_days),
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
        max_diff = int(getattr(settings, "RATING_LIMITS", {}).get("DUEL_MAX_RATING_DIFF", 150))
        if abs(request.user.rating_current - opponent.rating_current) > max_diff:
            return Response(
                {"detail": f"Rating difference must be {max_diff} or less."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        duel = Duel.objects.create(challenger=request.user, opponent=opponent, status=DuelStatus.PENDING)
        return Response(DuelSerializer(duel).data, status=status.HTTP_201_CREATED)


class DuelAcceptView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, duel_id: int, *args, **kwargs):
        duel = generics.get_object_or_404(Duel, id=duel_id, opponent=request.user)
        # Принять можно только приглашение, которое ещё ждёт ответа: раньше
        # статус не проверялся, и отклонённую дуэль можно было «принять»,
        # а принятую — принимать сколько угодно раз.
        if duel.status != DuelStatus.PENDING:
            return Response(
                {"detail": "Duel is not pending."}, status=status.HTTP_400_BAD_REQUEST
            )
        # resolved_at здесь не проставляется: принятая дуэль как раз и есть
        # активная. Раньше её ставили сразу, из-за чего проверка «одна активная
        # дуэль» не срабатывала никогда — дуэль переставала быть активной
        # в тот же момент, когда её приняли.
        duel.status = DuelStatus.ACCEPTED
        duel.save(update_fields=["status"])
        return Response(DuelSerializer(duel).data, status=status.HTTP_200_OK)


class DuelRejectView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, duel_id: int, *args, **kwargs):
        duel = generics.get_object_or_404(Duel, id=duel_id, opponent=request.user)
        if duel.status != DuelStatus.PENDING:
            return Response(
                {"detail": "Duel is not pending."}, status=status.HTTP_400_BAD_REQUEST
            )
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
        # Самонаставничество не отсекалось, а за него начисляются монеты
        # (MENTEE_WEEKLY_COINS) — можно было фармить их на себе.
        if mentee.pk == request.user.pk:
            return Response(
                {"detail": "Cannot mentor yourself."}, status=status.HTTP_400_BAD_REQUEST
            )

        limits = getattr(settings, "RATING_LIMITS", {})
        mentee_limit = int(limits.get("MENTORSHIP_ACTIVE_LIMIT", 5))

        # Лимит проверяется и подопечный заводится в одной транзакции с блокировкой
        # наставника: иначе параллельные запросы одинаково видят «место есть»
        # и набирают подопечных сверх лимита.
        with transaction.atomic():
            User.objects.select_for_update().filter(pk=request.user.pk).first()
            existing = Mentorship.objects.filter(mentor=request.user, mentee=mentee).first()
            if existing is not None:
                # Повторный запрос ничего не создаёт, поэтому и 201 здесь врал.
                return Response(MentorshipSerializer(existing).data, status=status.HTTP_200_OK)
            active_count = Mentorship.objects.filter(
                mentor=request.user, ended_at__isnull=True
            ).count()
            if mentee_limit > 0 and active_count >= mentee_limit:
                return Response(
                    {"detail": f"Mentee limit reached ({mentee_limit})."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            mentorship = Mentorship.objects.create(mentor=request.user, mentee=mentee)
        return Response(MentorshipSerializer(mentorship).data, status=status.HTTP_201_CREATED)

