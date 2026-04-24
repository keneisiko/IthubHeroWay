from rest_framework import serializers

from .models import User


class MeProfileSerializer(serializers.ModelSerializer):
    track = serializers.CharField(source="track.name", read_only=True)
    squad = serializers.CharField(source="squad.name", read_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "callsign",
            "avatar",
            "track",
            "squad",
            "level",
            "rating_current",
            "coins_balance",
        ]


class PublicProfileSerializer(serializers.ModelSerializer):
    track = serializers.CharField(source="track.name", read_only=True)
    squad = serializers.CharField(source="squad.name", read_only=True)
    rating_zone = serializers.SerializerMethodField()
    rating_current = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "username",
            "callsign",
            "avatar",
            "track",
            "squad",
            "level",
            "rating_zone",
            "rating_current",
        ]

    def get_rating_zone(self, obj: User) -> str:
        rating = obj.rating_current
        if rating < 100:
            return "red"
        if rating < 200:
            return "orange"
        if rating < 400:
            return "yellow"
        if rating < 650:
            return "green"
        if rating < 850:
            return "platinum"
        return "gold"

    def get_rating_current(self, obj: User):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        viewer: User = request.user
        if viewer.pk == obj.pk:
            return obj.rating_current
        # Extended visibility: curator for own squad, tutor/admin/hq globally.
        if viewer.role in {"tutor", "admin", "hq"}:
            return obj.rating_current
        if viewer.role == "curator" and viewer.squad_id and viewer.squad_id == obj.squad_id:
            return obj.rating_current
        # Public mode: no exact rating.
        return None

