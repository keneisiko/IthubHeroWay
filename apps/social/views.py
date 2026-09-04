from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsKnownRole
from apps.notifications.services import events

from .models import Duel, DuelStatus, Mentorship, Respect
from .serializers import (
    DuelCreateSerializer,
    DuelSerializer,
    MentorshipCreateSerializer,
    MentorshipSerializer,
    RespectCreateSerializer,
    RespectSerializer,
)
from .services.duels import (
    DuelNotAllowed,
    accept_duel,
    active_duels_q,
    cancel_duel,
    duel_bet,
    duel_duration_days,
    duel_wins,
    duels_for,
    reject_duel,
)
from .services.rewards import grant_mentorship_start_bonus, grant_respect_reward


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
            # Монеты получателю: коэффициент RESPECT_REWARD существовал
            # в настройках, но не начислялся нигде.
            granted = grant_respect_reward(respect)

        events.respect_received(respect, granted)
        payload = RespectSerializer(respect).data
        payload["coins_granted_to_recipient"] = granted
        return Response(payload, status=status.HTTP_201_CREATED)


class DuelCreateView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, *args, **kwargs):
        serializer = DuelCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        opponent = generics.get_object_or_404(User, username=serializer.validated_data["opponent_username"])
        if opponent.pk == request.user.pk:
            return Response({"detail": "Cannot duel yourself."}, status=status.HTTP_400_BAD_REQUEST)
        # One active duel at a time.
        active_q = active_duels_q()
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
        events.duel_invited(duel)
        return Response(DuelSerializer(duel).data, status=status.HTTP_201_CREATED)


class DuelListView(views.APIView):
    """Мои дуэли: входящие вызовы, идущие поединки и история.

    Без этого списка принять вызов из интерфейса было невозможно —
    эндпоинты приёма существовали, но узнать id дуэли было неоткуда.
    """

    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs):
        rows = duels_for(request.user)
        return Response(
            {
                "results": DuelSerializer(rows, many=True, context={"request": request}).data,
                "wins": duel_wins(request.user),
                "bet_coins": duel_bet(),
                "duration_days": duel_duration_days(),
                # Порог разницы рейтинга: интерфейс подсвечивает по нему,
                # кого можно вызвать, вместо отказа уже после нажатия.
                "max_rating_diff": int(
                    getattr(settings, "RATING_LIMITS", {}).get("DUEL_MAX_RATING_DIFF", 150)
                ),
                "my_rating": request.user.rating_current,
            }
        )


class DuelAcceptView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, duel_id: int, *args, **kwargs):
        try:
            duel = accept_duel(request.user, duel_id)
        except DuelNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        events.duel_answered(duel, accepted=True)
        return Response(DuelSerializer(duel).data, status=status.HTTP_200_OK)


class DuelRejectView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, duel_id: int, *args, **kwargs):
        try:
            duel = reject_duel(request.user, duel_id)
        except DuelNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        events.duel_answered(duel, accepted=False)
        return Response(DuelSerializer(duel).data, status=status.HTTP_200_OK)


class DuelCancelView(views.APIView):
    """Отозвать собственный вызов, пока на него не ответили."""

    permission_classes = [IsKnownRole]

    def post(self, request, duel_id: int, *args, **kwargs):
        try:
            duel = cancel_duel(request.user, duel_id)
        except DuelNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
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
            # Разовый рейтинг за взятого подшефного: коэффициент MENTORING
            # из блока «Движ» не начислялся нигде.
            grant_mentorship_start_bonus(mentorship)
        events.mentorship_started(mentorship)
        return Response(MentorshipSerializer(mentorship).data, status=status.HTTP_201_CREATED)


class MentorshipListView(views.APIView):
    """Мои подшефные и мои наставники.

    Раньше оформленное наставничество нигде не показывалось: студент нажимал
    «Стать наставником» и больше никогда не видел результата.
    """

    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs):
        rewards = getattr(settings, "QUESTS_REWARDS", {})
        mentees = Mentorship.objects.filter(mentor=request.user).select_related("mentee")
        mentors = Mentorship.objects.filter(mentee=request.user).select_related("mentor")
        return Response(
            {
                "mentees": MentorshipSerializer(mentees, many=True).data,
                "mentors": MentorshipSerializer(mentors, many=True).data,
                "weekly_coins_per_mentee": int(rewards.get("MENTEE_WEEKLY_COINS", 2)),
            }
        )


class MentorshipEndView(views.APIView):
    """Завершить наставничество: подшефный перестаёт числиться активным."""

    permission_classes = [IsKnownRole]

    def post(self, request, mentorship_id: int, *args, **kwargs):
        mentorship = generics.get_object_or_404(
            Mentorship, pk=mentorship_id, mentor=request.user, ended_at__isnull=True
        )
        mentorship.ended_at = timezone.now()
        mentorship.save(update_fields=["ended_at"])
        return Response(MentorshipSerializer(mentorship).data, status=status.HTTP_200_OK)
