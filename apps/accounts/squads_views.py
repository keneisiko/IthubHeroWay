from datetime import timedelta
from math import ceil

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from rest_framework import generics, status, views
from rest_framework.response import Response

from apps.operations.services.cache import invalidate_squad_leaderboard
from apps.progress.models import RatingLog
from apps.quests.models import Quest, QuestRewardTransaction, UserQuestProgress

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

# Без похожих друг на друга символов: код отряда люди диктуют и вводят руками.
CODE_SUFFIX_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"

TELEGRAM_REQUIRED_DETAIL = (
    "Сначала активируйте аккаунт в Telegram-боте командой /activate — "
    "без этого участие в рейтинге и отрядах недоступно."
)


def _has_active_telegram(user: User) -> bool:
    """Активна ли привязка Telegram.

    Раньше вместо проверки здесь стояла функция, которая молча создавала
    привязку с выдуманным telegram_user_id (5_100_000_000 + id пользователя).
    Это обходило гейт — а `telegram_link.is_active` определяет видимость
    во всех расчётах рейтинга — и рисковало столкнуться с реальным Telegram ID,
    который у живых аккаунтов давно перевалил за 5 млрд.
    """
    link = getattr(user, "telegram_link", None)
    return bool(link and link.is_active)


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
        if not _has_active_telegram(user):
            return Response({"detail": TELEGRAM_REQUIRED_DETAIL}, status=status.HTTP_403_FORBIDDEN)

        serializer = SquadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        name = data["name"].strip()
        base = (slugify(name) or "squad")[: Squad._meta.get_field("code").max_length - 8]

        # Подбор свободного кода через exists() + create() — гонка: два запроса
        # с одинаковым названием проходили проверку одновременно и второй падал
        # с IntegrityError наружу (500). Уникальность гарантирует только сама БД,
        # поэтому нарушение ловится и попытка повторяется с новым суффиксом.
        squad = None
        for attempt in range(10):
            code = base if attempt == 0 else f"{base}-{get_random_string(6, CODE_SUFFIX_ALPHABET)}"
            try:
                with transaction.atomic():
                    squad = Squad.objects.create(
                        code=code,
                        name=name,
                        course=data.get("course"),
                        capacity=data.get("capacity", 20),
                    )
            except IntegrityError:
                continue
            break
        if squad is None:
            return Response(
                {"detail": "Could not allocate a squad code, try again."},
                status=status.HTTP_409_CONFLICT,
            )

        user.squad = squad
        user.save(update_fields=["squad"])
        invalidate_squad_leaderboard()

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
        if not _has_active_telegram(user):
            return Response({"detail": TELEGRAM_REQUIRED_DETAIL}, status=status.HTTP_403_FORBIDDEN)

        serializer = SquadJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"].strip().lower()

        # Подсчёт мест и запись пользователя идут одной транзакцией с блокировкой
        # строки отряда: без неё два параллельных запроса считали агентов
        # одновременно, оба видели свободное место и отряд переполнялся сверх
        # capacity. Блокируется именно отряд — он общий для конкурирующих
        # запросов, тогда как строки пользователей у них разные.
        with transaction.atomic():
            squad = Squad.objects.select_for_update().filter(code__iexact=code).first()
            if not squad:
                return Response({"detail": "Squad not found."}, status=status.HTTP_404_NOT_FOUND)

            agents_count = User.objects.filter(
                squad=squad, role=Role.AGENT, telegram_link__is_active=True
            ).count()
            if squad.capacity is not None and agents_count >= squad.capacity:
                return Response({"detail": "Squad is full."}, status=status.HTTP_400_BAD_REQUEST)

            user.squad = squad
            user.save(update_fields=["squad"])
        invalidate_squad_leaderboard()

        return Response({"code": squad.code, "name": squad.name})


class SquadLeaveView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, *args, **kwargs):
        user: User = request.user
        if not user.squad_id:
            return Response({"detail": "You are not in a squad."}, status=status.HTTP_400_BAD_REQUEST)
        user.squad = None
        user.save(update_fields=["squad"])
        invalidate_squad_leaderboard()
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

        # Место в рейтинге считается в БД. Раньше сюда загружались все отряды
        # с агрегатом, место искалось перебором в Python, а `.count()` по тому же
        # queryset выполнял агрегат второй раз — и всё это на каждый запрос.
        squads_stats = Squad.objects.annotate(
            avg_rating=Avg(
                "members__rating_current",
                filter=Q(members__role="agent", members__telegram_link__is_active=True),
            )
        )
        own = squads_stats.filter(id=squad.id).first()
        own_avg = (own.avg_rating if own else None) or 0
        better = squads_stats.filter(avg_rating__gt=own_avg).count()
        squad_place = better + 1
        total_squads = Squad.objects.count()

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
        limits = getattr(settings, "RATING_LIMITS", {})
        bonus_percent = int(limits.get("SQUAD_WEEKLY_BONUS_PERCENT", 80))
        bonus_coins = int(limits.get("SQUAD_WEEKLY_BONUS_COINS", 5))
        bonus_share = bonus_percent / 100

        weekly_percent = (weekly_completed / agents_count) if agents_count else 0
        weekly_bonus_active = weekly_percent >= bonus_share
        weekly_remaining = (
            max(0, ceil(bonus_share * agents_count) - weekly_completed) if agents_count else 0
        )

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
                "bonus_threshold_percent": bonus_percent,
                "bonus_reward_coins": bonus_coins,
                "status": "active" if weekly_bonus_active else "not_ready",
                "remaining_to_threshold": weekly_remaining,
            },
            "actions": {
                "share_url": f"/squads/{squad.code}",
                "month_coins": int(month_coins),
            },
        }
        return Response(data)


class SquadMembersView(views.APIView):
    """Список участников отряда.

    Раньше класс наследовался от ListAPIView, но целиком переопределял get(),
    так что ни пагинация, ни serializer_class не работали — фронт получал
    плоский список и мог считать, что где-то есть постранично. Базовый класс
    приведён в соответствие с реальным поведением; сериализатор здесь зависит
    от того, свой отряд смотрит пользователь или чужой.
    """

    permission_classes = [IsKnownRole]

    # Длинная строка поиска бессмысленна (позывной короче) и заставляет БД
    # гонять LIKE по мусору, поэтому обрезается.
    MAX_SEARCH_LENGTH = 50

    def get(self, request, code: str, *args, **kwargs):
        user: User = request.user
        squad = generics.get_object_or_404(Squad, code=code)

        qs = User.objects.filter(squad=squad, telegram_link__is_active=True).select_related("track")

        search = (request.query_params.get("search") or "").strip()[: self.MAX_SEARCH_LENGTH]
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

    # Верхняя граница нужна и от опечаток, и от разрастания ключей кеша:
    # раньше `?limit=abc` давал 500, а `?limit=999999` — выборку без предела.
    MAX_LIMIT = 100
    DEFAULT_LIMIT = 20

    def get(self, request, *args, **kwargs):
        raw_limit = request.query_params.get("limit", self.DEFAULT_LIMIT)
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = self.DEFAULT_LIMIT
        limit = max(1, min(limit, self.MAX_LIMIT))

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
