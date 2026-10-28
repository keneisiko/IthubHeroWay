from rest_framework import serializers

from apps.operations.services.platform_settings import platform_setting

from .models import OrderStatus, Purchase, ShopItem


class ShopItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopItem
        fields = [
            "id",
            "code",
            "title",
            "description",
            "item_type",
            "slot",
            "price_coins",
            "stock",
            "is_active",
            "available_from",
            "available_to",
        ]


class PurchaseSerializer(serializers.ModelSerializer):
    item = ShopItemSerializer(read_only=True)
    # Интерфейсу нужно знать, надета ли покупка: кнопка переключается между
    # «Применить» и «Снять».
    is_applied = serializers.BooleanField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    pickup_info = serializers.SerializerMethodField()

    class Meta:
        model = Purchase
        fields = [
            "id",
            "item",
            "coins_spent",
            "created_at",
            "applied_at",
            "is_applied",
            "consumed_at",
            "meta",
            "status",
            "status_display",
            "status_changed_at",
            "pickup_info",
        ]

    def get_pickup_info(self, obj: Purchase) -> str:
        """Где забрать — только пока заказ ждёт выдачи."""
        if obj.status not in (OrderStatus.ORDERED, OrderStatus.READY):
            return ""
        return platform_setting("shop_pickup_info")


class PurchaseCreateSerializer(serializers.Serializer):
    item_code = serializers.CharField(max_length=64)
    meta = serializers.JSONField(required=False)

