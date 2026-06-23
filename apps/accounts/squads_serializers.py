from rest_framework import serializers

from .models import Squad, Track, User


class SquadMeWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Squad
        fields = ["code", "name", "course", "capacity"]


class SquadListSerializer(serializers.ModelSerializer):
    agents_count = serializers.IntegerField(read_only=True)
    avg_rating = serializers.FloatField(read_only=True)
    can_join = serializers.SerializerMethodField()

    class Meta:
        model = Squad
        fields = ["code", "name", "course", "capacity", "agents_count", "avg_rating", "can_join"]

    def get_can_join(self, obj: Squad) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        user: User = request.user
        if user.squad_id:
            return False
        agents_count = getattr(obj, "agents_count", 0) or 0
        if obj.capacity is not None and agents_count >= obj.capacity:
            return False
        return True


class SquadJoinSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)


class SquadCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    course = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=6)
    capacity = serializers.IntegerField(required=False, min_value=2, max_value=100, default=20)


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
