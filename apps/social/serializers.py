from rest_framework import serializers

from .models import Duel, Mentorship, Respect


class RespectCreateSerializer(serializers.Serializer):
    to_username = serializers.CharField(max_length=150)
    message = serializers.CharField(required=False, allow_blank=True, max_length=255)


class RespectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Respect
        fields = ["id", "from_user", "to_user", "message", "created_at"]


class DuelCreateSerializer(serializers.Serializer):
    opponent_username = serializers.CharField(max_length=150)


class DuelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Duel
        fields = ["id", "challenger", "opponent", "status", "created_at", "resolved_at"]


class MentorshipCreateSerializer(serializers.Serializer):
    mentee_username = serializers.CharField(max_length=150)


class MentorshipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mentorship
        fields = ["id", "mentor", "mentee", "started_at", "ended_at"]

