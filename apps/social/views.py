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
from apps.operations.api_guard import accruals_off_response
from apps.operations.services.platform_settings import platform_setting

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
from .services.mentorship import (
    MentorshipNotAllowed,
    accept_mentorship,
    decline_mentorship,
    end_mentorship,
    next_request_at,
    request_mentorship,
)
from .services.rewards import MENTOR_CAP_PER_MENTEE, MENTOR_SHARE, grant_respect_reward


class RespectCreateView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, *args, **kwargs):
        blocked = accruals_off_response()
        if blocked is not None:
            return blocked
        serializer = RespectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        to_user = generics.get_object_or_404(User, username=serializer.validated_data["to_username"])
        if to_user.pk == request.user.pk:
            return Response({"detail": "Cannot send respect to yourself."}, status=status.HTTP_400_BAD_REQUEST)
        limits = getattr(settings, "RATING_LIMITS", {})
        respect_weekly = int(platform_setting("respect_weekly_limit"))
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
        blocked = accruals_off_response()
        if blocked is not None:
            return blocked
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
        max_diff = int(platform_setting("duel_max_rating_diff"))
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
                "max_rating_diff": int(platform_setting("duel_max_rating_diff")),
                "my_rating": request.user.rating_current,
            }
        )


class DuelAcceptView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, duel_id: int, *args, **kwargs):
        blocked = accruals_off_response()
        if blocked is not None:
            return blocked
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
    """Предложить шефство. Действует только после согласия подшефного."""

    permission_classes = [IsKnownRole]

    def post(self, request, *args, **kwargs):
        blocked = accruals_off_response()
        if blocked is not None:
            return blocked
        serializer = MentorshipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mentee = generics.get_object_or_404(User, username=serializer.validated_data["mentee_username"])
        try:
            mentorship = request_mentorship(request.user, mentee)
        except MentorshipNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        events.mentorship_requested(mentorship)
        return Response(MentorshipSerializer(mentorship).data, status=status.HTTP_201_CREATED)


class MentorshipAnswerView(views.APIView):
    """Подшефный принимает или отклоняет предложение."""

    permission_classes = [IsKnownRole]
    accept = True

    def post(self, request, mentorship_id: int, *args, **kwargs):
        blocked = accruals_off_response()
        if blocked is not None:
            return blocked
        action = accept_mentorship if self.accept else decline_mentorship
        try:
            mentorship = action(request.user, mentorship_id)
        except MentorshipNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        events.mentorship_answered(mentorship, accepted=self.accept)
        return Response(MentorshipSerializer(mentorship).data, status=status.HTTP_200_OK)


class MentorshipListView(views.APIView):
    """Мои подшефные и мои наставники.

    Раньше оформленное наставничество нигде не показывалось: студент нажимал
    «Стать наставником» и больше никогда не видел результата.
    """

    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs):
        mentees = Mentorship.objects.filter(mentor=request.user).select_related("mentee")
        mentors = Mentorship.objects.filter(mentee=request.user).select_related("mentor")
        return Response(
            {
                "mentees": MentorshipSerializer(mentees, many=True).data,
                "mentors": MentorshipSerializer(mentors, many=True).data,
                # Как наставник зарабатывает: доля от недельных успехов подшефного.
                "mentor_share_percent": int(MENTOR_SHARE * 100),
                "mentor_cap_per_mentee": int(MENTOR_CAP_PER_MENTEE),
                "next_request_at": next_request_at(request.user),
            }
        )


class MentorshipEndView(views.APIView):
    """Завершить шефство (любая сторона) или отозвать своё предложение."""

    permission_classes = [IsKnownRole]

    def post(self, request, mentorship_id: int, *args, **kwargs):
        try:
            mentorship = end_mentorship(request.user, mentorship_id)
        except MentorshipNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(MentorshipSerializer(mentorship).data, status=status.HTTP_200_OK)
