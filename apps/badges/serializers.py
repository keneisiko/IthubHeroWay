from rest_framework import serializers

from .models import Badge, UserBadge


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = [
            "id",
            "code",
            "title",
            "description",
            "category",
            "rarity",
            "condition",
            "reward_coins",
            "is_active",
        ]


class UserBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ["id", "badge", "acquired_at", "is_pinned", "source"]

