from rest_framework import serializers

from .models import Purchase, ShopItem


class ShopItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopItem
        fields = [
            "id",
            "code",
            "title",
            "description",
            "item_type",
            "price_coins",
            "is_active",
            "available_from",
            "available_to",
        ]


class PurchaseSerializer(serializers.ModelSerializer):
    item = ShopItemSerializer(read_only=True)

    class Meta:
        model = Purchase
        fields = ["id", "item", "coins_spent", "created_at", "meta"]


class PurchaseCreateSerializer(serializers.Serializer):
    item_code = serializers.CharField(max_length=64)
    meta = serializers.JSONField(required=False)

