from rest_framework import serializers

from apps.accounts.models import User

from .models import Duel, Mentorship, Respect


class UserBriefSerializer(serializers.ModelSerializer):
    """Участник соц-действия в ответе API.

    Раньше отдавался голый первичный ключ: клиенту нечего с ним делать,
    приходилось ходить за именем отдельным запросом.
    """

    class Meta:
        model = User
        fields = ["username", "callsign"]
        read_only_fields = fields


class RespectCreateSerializer(serializers.Serializer):
    to_username = serializers.CharField(max_length=150)
    message = serializers.CharField(required=False, allow_blank=True, max_length=255)


class RespectSerializer(serializers.ModelSerializer):
    from_user = UserBriefSerializer(read_only=True)
    to_user = UserBriefSerializer(read_only=True)

    class Meta:
        model = Respect
        fields = ["id", "from_user", "to_user", "message", "created_at"]


class DuelCreateSerializer(serializers.Serializer):
    opponent_username = serializers.CharField(max_length=150)


class DuelSerializer(serializers.ModelSerializer):
    challenger = UserBriefSerializer(read_only=True)
    opponent = UserBriefSerializer(read_only=True)

    class Meta:
        model = Duel
        fields = ["id", "challenger", "opponent", "status", "created_at", "resolved_at"]


class MentorshipCreateSerializer(serializers.Serializer):
    mentee_username = serializers.CharField(max_length=150)


class MentorshipSerializer(serializers.ModelSerializer):
    mentor = UserBriefSerializer(read_only=True)
    mentee = UserBriefSerializer(read_only=True)

    class Meta:
        model = Mentorship
        fields = ["id", "mentor", "mentee", "started_at", "ended_at"]

