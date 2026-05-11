from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from rest_framework import generics, status, views
from rest_framework.response import Response

from apps.accounts.permissions import IsKnownRole
from apps.progress.models import RatingChangeSource
from apps.progress.services.rewards import apply_rating_delta_with_cap, remaining_daily_coin_budget
from .models import Quest, QuestRewardTransaction, UserQuestProgress
from .serializers import (
    CompleteQuestSerializer,
    QuestSerializer,
    QuestRewardTransactionSerializer,
    UpdateQuestProgressSerializer,
    UserQuestProgressSerializer,
)


class ActiveQuestListView(generics.ListAPIView):
    permission_classes = [IsKnownRole]
    serializer_class = QuestSerializer

    def get_queryset(self):
        now = timezone.now()
        queryset = Quest.objects.filter(is_active=True).filter(
            start_at__isnull=True
        ) | Quest.objects.filter(is_active=True, start_at__lte=now)
        quest_type = self.request.query_params.get("quest_type")
        if quest_type:
            queryset = queryset.filter(quest_type=quest_type)
        return queryset.order_by("id")


class MyQuestProgressListView(generics.ListAPIView):
    permission_classes = [IsKnownRole]
    serializer_class = UserQuestProgressSerializer

    def get_queryset(self):
        queryset = UserQuestProgress.objects.filter(user=self.request.user).select_related("quest")
        completed = self.request.query_params.get("completed")
        if completed in {"true", "false"}:
            queryset = queryset.filter(is_completed=(completed == "true"))
        return queryset.order_by("-updated_at")


class QuestProgressUpdateView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, code: str) -> Response:
        serializer = UpdateQuestProgressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quest = generics.get_object_or_404(Quest, code=code, is_active=True)
        progress, _ = UserQuestProgress.objects.get_or_create(user=request.user, quest=quest)
        data = serializer.validated_data

        if "progress_value" in data:
            progress.progress_value = data["progress_value"]
        if "proof_payload" in data:
            progress.proof_payload = data["proof_payload"]

        progress.save(update_fields=["progress_value", "proof_payload", "updated_at"])
        return Response(UserQuestProgressSerializer(progress).data, status=status.HTTP_200_OK)


class QuestCompleteView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, code: str) -> Response:
        serializer = CompleteQuestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            quest = generics.get_object_or_404(Quest, code=code, is_active=True)
            progress, _ = UserQuestProgress.objects.select_for_update().get_or_create(
                user=request.user, quest=quest
            )

            progress.is_completed = True
            progress.progress_value = max(progress.progress_value, 1)
            progress.completed_at = timezone.now()
            if "proof_payload" in serializer.validated_data:
                progress.proof_payload = serializer.validated_data["proof_payload"]
            progress.save(
                update_fields=["is_completed", "progress_value", "completed_at", "proof_payload", "updated_at"]
            )

            reward_tx, created = QuestRewardTransaction.objects.get_or_create(
                user=request.user,
                quest=quest,
                defaults={
                    "progress": progress,
                    "coins_delta": quest.reward_coins,
                    "rating_delta": quest.reward_rating_delta,
                },
            )

            # Idempotency guard: reward is granted only once per (user, quest).
            if created:
                user = request.user
                allowed_coins = min(reward_tx.coins_delta, remaining_daily_coin_budget(user))
                if allowed_coins:
                    user.coins_balance += allowed_coins
                    user.save(update_fields=["coins_balance"])
                apply_rating_delta_with_cap(
                    user=user,
                    delta=reward_tx.rating_delta,
                    source=RatingChangeSource.QUEST,
                    reason=f"Quest complete: {quest.code}",
                    source_id=str(quest.id),
                )
                cache.delete(f"profile:{user.username}")
                cache.delete_pattern("leaderboard:*")

        return Response(UserQuestProgressSerializer(progress).data, status=status.HTTP_200_OK)


class QuestRewardHistoryView(generics.ListAPIView):
    permission_classes = [IsKnownRole]
    serializer_class = QuestRewardTransactionSerializer

    def get_queryset(self):
        return QuestRewardTransaction.objects.filter(user=self.request.user).select_related("quest").order_by(
            "-granted_at"
        )

