from rest_framework import serializers

from apps.accounts.frames import resolve_frame
from apps.accounts.models import User

from .models import RatingLog


class RatingLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RatingLog
        fields = [
            "id",
            "value_before",
            "value_after",
            "delta",
            "source",
            "source_id",
            "reason",
            "created_at",
        ]


class RatingMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "callsign", "rating_current", "coins_balance", "level"]


class LeaderboardAgentSerializer(serializers.ModelSerializer):
    # код применённого косметического товара (рамка аватара) или null
    applied_cosmetic = serializers.CharField(read_only=True, allow_null=True, default=None)
    # итоговая рамка: от нашивки (разработчик) или купленная фиолетовая
    avatar_frame = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["username", "callsign", "avatar", "applied_cosmetic", "avatar_frame", "rating_current", "level"]

    def get_avatar_frame(self, obj: User) -> str:
        return resolve_frame(getattr(obj, "badge_frame", None), getattr(obj, "applied_cosmetic", None))

