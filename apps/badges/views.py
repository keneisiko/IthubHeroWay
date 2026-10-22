from django.db.models import Count, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, views
from rest_framework.response import Response

from apps.accounts.models import Role, User
from apps.accounts.permissions import IsKnownRole
from apps.operations.services.cache import invalidate_leaderboards, invalidate_profile
from apps.shop.models import Purchase, ShopItemSlot

from .models import Badge, UserBadge
from .serializers import BadgeHolderSerializer, BadgeSerializer, UserBadgeSerializer
from .services import award_badges_for_user


class BadgeListView(generics.ListAPIView):
    # Сайт читает только первую страницу ответа, а по умолчанию она — 20
    # записей: 25-ю нашивку студент не видел, выполненные квесты после 20-го
    # возвращались в «активные». Список личный или каталожный — отдаём целиком.
    pagination_class = None
    permission_classes = [IsKnownRole]
    serializer_class = BadgeSerializer

    def get_queryset(self):
        # Считаем только активированных студентов: неактивированные импорты
        # (их сотни) нашивок получить не могут и занижали бы долю.
        return (
            Badge.objects.filter(is_active=True)
            .annotate(
                owners_count=Count(
                    "awarded_users",
                    filter=Q(awarded_users__user__role=Role.AGENT, awarded_users__user__is_active=True),
                    distinct=True,
                )
            )
            .order_by("id")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["students_total"] = User.objects.filter(role=Role.AGENT, is_active=True).count()
        return context


class MyBadgeListView(generics.ListAPIView):
    # Сайт читает только первую страницу ответа, а по умолчанию она — 20
    # записей: 25-ю нашивку студент не видел, выполненные квесты после 20-го
    # возвращались в «активные». Список личный или каталожный — отдаём целиком.
    pagination_class = None
    permission_classes = [IsKnownRole]
    serializer_class = UserBadgeSerializer

    def get_queryset(self):
        return UserBadge.objects.filter(user=self.request.user).select_related("badge").order_by("-acquired_at")


class BadgePinView(views.APIView):
    """Закрепить значок в профиле или снять закрепление.

    Раньше был только POST, который выставлял `is_pinned = True`: открепить
    значок было нельзя ни через API, ни из интерфейса — закрепив три,
    студент оставался с ними навсегда.
    """

    permission_classes = [IsKnownRole]

    def _get_badge(self, request, code: str) -> UserBadge:
        return generics.get_object_or_404(
            UserBadge.objects.select_related("badge"), user=request.user, badge__code=code
        )

    def _set_pinned(self, request, code: str, pinned: bool) -> Response:
        user_badge = self._get_badge(request, code)
        user_badge.is_pinned = pinned
        user_badge.save(update_fields=["is_pinned"])
        # закреплённая нашивка с рамкой меняет аватар в профиле и рейтингах
        if user_badge.badge.avatar_frame:
            invalidate_profile(request.user.username)
            invalidate_leaderboards()
        return Response(UserBadgeSerializer(user_badge).data, status=status.HTTP_200_OK)

    def post(self, request, code: str) -> Response:
        return self._set_pinned(request, code, True)

    def delete(self, request, code: str) -> Response:
        return self._set_pinned(request, code, False)


class BadgeAwardCheckView(views.APIView):
    permission_classes = [IsKnownRole]
    # Проверка перебирает все активные значки с запросом на каждый,
    # поэтому без ограничения частоты эндпоинт работает генератором нагрузки.
    throttle_scope = "heavy"

    def post(self, request, *args, **kwargs) -> Response:
        awarded = award_badges_for_user(request.user)
        return Response({"awarded_count": len(awarded)}, status=status.HTTP_200_OK)



class BadgeHoldersView(views.APIView):
    """Кто получил нашивку — для кнопки «У кого есть» в её карточке.

    Как и рейтинг, показывает только активных студентов: сотрудники и
    отключённые аккаунты в списке не нужны. Первыми — кто получил раньше.
    """

    permission_classes = [IsKnownRole]
    LIMIT = 100

    def get(self, request, code: str) -> Response:
        badge = get_object_or_404(Badge, code=code, is_active=True)
        # рамка аватара одним подзапросом на строку, как в рейтинге
        badge_frame = (
            UserBadge.objects.filter(user=OuterRef("user"), is_pinned=True)
            .exclude(badge__avatar_frame="")
            .order_by("acquired_at")
            .values("badge__avatar_frame")[:1]
        )
        applied_cosmetic = (
            Purchase.objects.filter(
                user=OuterRef("user"), applied_at__isnull=False, item__slot=ShopItemSlot.AVATAR_FRAME
            )
            .order_by("-applied_at")
            .values("item__code")[:1]
        )
        holders = (
            UserBadge.objects.filter(badge=badge, user__role=Role.AGENT, user__is_active=True)
            .select_related("user", "user__squad")
            .annotate(badge_frame=Subquery(badge_frame), applied_cosmetic=Subquery(applied_cosmetic))
            .order_by("acquired_at", "id")
        )
        rows = BadgeHolderSerializer(holders[: self.LIMIT], many=True, context={"request": request}).data
        return Response({"count": holders.count(), "results": rows})
