from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.response import Response

from apps.accounts.permissions import IsKnownRole
from apps.notifications.services import events
from apps.progress.services.rewards import local_day_start

from .models import (
    Quest,
    QuestRewardTransaction,
    QuestType,
    SelfReportProof,
    SelfReportProofStatus,
    UserQuestProgress,
)
from .serializers import (
    CompleteQuestSerializer,
    QuestRewardTransactionSerializer,
    QuestSerializer,
    SelfReportCreateSerializer,
    UpdateQuestProgressSerializer,
    UserQuestProgressSerializer,
)
from .services.quest_conditions import is_manual_complete_allowed
from .services.quest_periods import quests_for_date
from .services.weekly_focus import FocusNotAllowed, current_period_key, get_focus, set_focus


class ActiveQuestListView(generics.ListAPIView):
    permission_classes = [IsKnownRole]
    serializer_class = QuestSerializer

    def get_queryset(self):
        """Квесты, действующие сегодня.

        Раньше проверялось только начало окна, а `end_at` игнорировался:
        вчерашний ежедневный квест и позапрошлая неделя оставались «активными»
        навсегда, показывая «осталось 0 дн.». С экземплярами на период таких
        карточек становилось по одной за каждый прошедший день.
        """
        quest_type = self.request.query_params.get("quest_type")
        return quests_for_date(timezone.localdate(), [quest_type] if quest_type else None)


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
        if not is_manual_complete_allowed(quest):
            return Response(
                {"detail": "Progress for this quest is updated automatically."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        progress, _ = UserQuestProgress.objects.get_or_create(user=request.user, quest=quest)
        data = serializer.validated_data

        if "progress_value" in data:
            progress.progress_value = data["progress_value"]
        if "proof_payload" in data:
            progress.proof_payload = data["proof_payload"]

        progress.save(update_fields=["progress_value", "proof_payload", "updated_at"])
        return Response(UserQuestProgressSerializer(progress).data, status=status.HTTP_200_OK)


class QuestCompleteView(views.APIView):
    """Заявка на подтверждение квеста, а не мгновенное закрытие.

    Раньше нажатие «Подтвердить» сразу засчитывало квест и начисляло монеты
    с рейтингом: ссылку-доказательство никто не смотрел, и любой квест
    с ручным подтверждением был источником бесплатной награды.

    Теперь запрос создаёт заявку со статусом «на проверке». Награда
    начисляется, когда куратор одобрит её в админке.
    """

    permission_classes = [IsKnownRole]
    throttle_scope = "heavy"

    def post(self, request, code: str) -> Response:
        serializer = CompleteQuestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        now = timezone.now()
        quest = generics.get_object_or_404(Quest, code=code, is_active=True)
        if not is_manual_complete_allowed(quest):
            return Response(
                {
                    "detail": (
                        "Этот квест проверяется автоматически по данным Hik/LXP/YouGile. "
                        "Выполните условие и дождитесь проверки."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if quest.end_at and quest.end_at < now:
            return Response({"detail": "Срок квеста уже истёк."}, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data.get("proof_payload") or {}
        link = str(payload.get("link") or "").strip()
        comment = str(payload.get("comment") or "").strip()

        with transaction.atomic():
            progress, _ = UserQuestProgress.objects.get_or_create(user=request.user, quest=quest)
            if progress.is_completed:
                return Response({"detail": "Квест уже выполнен."}, status=status.HTTP_400_BAD_REQUEST)

            proof, created = SelfReportProof.objects.get_or_create(
                quest_progress=progress,
                defaults={
                    "quest": quest,
                    "user": request.user,
                    "comment": comment or f"Подтверждение квеста «{quest.title}»",
                    "attachment_link": link,
                    "status": SelfReportProofStatus.PENDING,
                },
            )
            if not created:
                if proof.status == SelfReportProofStatus.APPROVED:
                    return Response(
                        {"detail": "Подтверждение уже одобрено."}, status=status.HTTP_400_BAD_REQUEST
                    )
                # Повторная отправка обновляет заявку: студент мог приложить
                # не ту ссылку или получить отказ и исправиться.
                proof.comment = comment or proof.comment
                proof.attachment_link = link or proof.attachment_link
                proof.status = SelfReportProofStatus.PENDING
                proof.reviewed_by = None
                proof.reviewed_at = None
                proof.save(
                    update_fields=["comment", "attachment_link", "status", "reviewed_by", "reviewed_at"]
                )

        events.proof_submitted(proof)
        return Response(
            {
                "status": proof.status,
                "proof_id": proof.pk,
                "detail": "Отправлено на проверку куратору.",
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class QuestRewardHistoryView(generics.ListAPIView):
    permission_classes = [IsKnownRole]
    serializer_class = QuestRewardTransactionSerializer

    def get_queryset(self):
        return QuestRewardTransaction.objects.filter(user=self.request.user).select_related("quest").order_by(
            "-granted_at"
        )


class SelfReportCreateView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, code: str) -> Response:
        serializer = SelfReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        now = timezone.now()
        quest = generics.get_object_or_404(Quest, code=code, is_active=True)
        if quest.quest_type not in {QuestType.SELF_REPORT, QuestType.MIXED}:
            return Response({"detail": "Quest does not accept self-reports."}, status=status.HTTP_400_BAD_REQUEST)
        if quest.start_at and quest.start_at > now:
            return Response({"detail": "Quest is not started yet."}, status=status.HTTP_400_BAD_REQUEST)
        if quest.end_at and quest.end_at < now:
            return Response({"detail": "Quest is already ended."}, status=status.HTTP_400_BAD_REQUEST)

        progress, _ = UserQuestProgress.objects.get_or_create(user=request.user, quest=quest)
        if progress.is_completed:
            return Response({"detail": "Quest is already completed."}, status=status.HTTP_400_BAD_REQUEST)

        from django.conf import settings

        max_daily = int(getattr(settings, "RATING_LIMITS", {}).get("MAX_DAILY_SELF_REPORTS", 3))
        # Полночь по Москве, а не по UTC: иначе лимит самоотчётов сбрасывается
        # в 03:00 местного времени.
        day_start = local_day_start(now)
        today_count = SelfReportProof.objects.filter(user=request.user, created_at__gte=day_start).count()
        if today_count >= max_daily:
            return Response(
                {"detail": f"Daily self-report limit reached ({max_daily}/day)."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        last = SelfReportProof.objects.filter(user=request.user).order_by("-created_at").first()
        if last and (now - last.created_at).total_seconds() < 5 * 60:
            return Response({"detail": "Too frequent. Try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        proof, created = SelfReportProof.objects.get_or_create(
            quest=quest,
            user=request.user,
            quest_progress=progress,
            defaults={"comment": serializer.validated_data["comment"], "status": SelfReportProofStatus.PENDING},
        )
        if not created:
            if proof.status == SelfReportProofStatus.PENDING:
                proof.comment = serializer.validated_data["comment"]
                proof.save(update_fields=["comment"])
            return Response({"status": proof.status, "proof_id": proof.id}, status=status.HTTP_200_OK)

        events.proof_submitted(proof)
        return Response({"status": "pending", "proof_id": proof.id}, status=status.HTTP_201_CREATED)

class WeeklyFocusView(views.APIView):
    """Цель недели: какой еженедельный квест студент выбрал приоритетным.

    Раньше блок «Еженедельный выбор» хранил выбор только в состоянии React —
    он не доживал до перезагрузки страницы и ни на что не влиял.
    """

    permission_classes = [IsKnownRole]

    def get(self, request) -> Response:
        focus = get_focus(request.user)
        rewards = getattr(settings, "QUESTS_REWARDS", {})
        return Response(
            {
                "period_key": current_period_key(),
                "quest_code": focus.quest.code if focus else "",
                "quest_title": focus.quest.title if focus else "",
                "bonus_coins": int(rewards.get("WEEKLY_FOCUS_BONUS_COINS", 5)),
                "bonus_rating": int(rewards.get("WEEKLY_FOCUS_BONUS_RATING", 3)),
            }
        )

    def post(self, request) -> Response:
        quest_code = str(request.data.get("quest_code") or "").strip()
        if not quest_code:
            return Response({"detail": "Не передан код квеста."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            focus = set_focus(request.user, quest_code)
        except FocusNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"period_key": focus.period_key, "quest_code": focus.quest.code, "quest_title": focus.quest.title}
        )
