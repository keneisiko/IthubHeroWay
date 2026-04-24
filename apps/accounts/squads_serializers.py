from rest_framework import serializers

from .models import Squad, Track, User


class SquadMeWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Squad
        fields = ["code", "name", "course", "capacity"]


class SquadMemberSerializer(serializers.ModelSerializer):
    track = serializers.CharField(source="track.code", read_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "callsign",
            "avatar",
            "track",
            "status",
            "role",
            "rating_current",
        ]


class SquadMemberPublicSerializer(serializers.ModelSerializer):
    track = serializers.CharField(source="track.code", read_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "callsign",
            "avatar",
            "track",
            "status",
            "role",
        ]

