from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsKnownRole
from apps.operations.services.cache import invalidate_profile

from .models import Purchase, ShopItem
from .serializers import PurchaseCreateSerializer, PurchaseSerializer, ShopItemSerializer


class ShopItemListView(generics.ListAPIView):
    permission_classes = [IsKnownRole]
    serializer_class = ShopItemSerializer

    def get_queryset(self):
        now = timezone.now()
        queryset = ShopItem.objects.filter(is_active=True).filter(
            available_from__isnull=True
        ) | ShopItem.objects.filter(
            is_active=True,
            available_from__lte=now,
        )
        item_type = self.request.query_params.get("item_type")
        if item_type:
            queryset = queryset.filter(item_type=item_type)
        return queryset.order_by("id")


class PurchaseCreateView(views.APIView):
    permission_classes = [IsKnownRole]

    def post(self, request, *args, **kwargs):
        serializer = PurchaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item_code = serializer.validated_data["item_code"]
        item = generics.get_object_or_404(ShopItem, code=item_code, is_active=True)
        now = timezone.now()
        if item.available_from and item.available_from > now:
            return Response({"detail": "Item is not available yet."}, status=status.HTTP_400_BAD_REQUEST)
        if item.available_to and item.available_to < now:
            return Response({"detail": "Item is no longer available."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if user.coins_balance < item.price_coins:
                return Response({"detail": "Insufficient coins."}, status=status.HTTP_400_BAD_REQUEST)

            user.coins_balance -= item.price_coins
            user.save(update_fields=["coins_balance"])

            purchase = Purchase.objects.create(
                user=user,
                item=item,
                coins_spent=item.price_coins,
                meta=serializer.validated_data.get("meta", {}),
            )
            invalidate_profile(user.username)

        return Response(PurchaseSerializer(purchase).data, status=status.HTTP_201_CREATED)


class MyPurchaseListView(generics.ListAPIView):
    permission_classes = [IsKnownRole]
    serializer_class = PurchaseSerializer

    def get_queryset(self):
        return Purchase.objects.filter(user=self.request.user).select_related("item").order_by("-created_at")

