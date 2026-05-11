from rest_framework import serializers

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
    class Meta:
        model = User
        fields = ["username", "callsign", "rating_current", "level"]

