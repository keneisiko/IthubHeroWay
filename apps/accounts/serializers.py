from rest_framework import serializers

from apps.badges.serializers import PublicUserBadgeSerializer
from apps.progress.services.path_map import path_reached
from apps.progress.services.pillar_labels import characteristics_payload
from apps.progress.services.rating_zones import rating_status_label, rating_zone
from apps.shop.services import applied_purchases
from apps.social.services.duels import duel_wins
from apps.social.services.rewards import respects_received_count

from .models import User


class MeProfileSerializer(serializers.ModelSerializer):
    track = serializers.CharField(source="track.name", read_only=True)
    squad = serializers.CharField(source="squad.name", read_only=True)
    # Карта пути в профиле: без этого поля фронт подставлял ['entry'] всем.
    path_reached = serializers.SerializerMethodField()
    # Активные покупки: какая рамка аватара и какое свечение значка надеты.
    applied_items = serializers.SerializerMethodField()
    duel_wins = serializers.SerializerMethodField()
    respects_received = serializers.SerializerMethodField()
    # Статус по разделу 8 Положения: его название, а не только код зоны.
    rating_status = serializers.SerializerMethodField()
    # п. 2.1: принял ли студент действующую редакцию Положения.
    policy_accepted = serializers.SerializerMethodField()

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
            "rating_status",
            "coins_balance",
            "path_reached",
            "applied_items",
            "duel_wins",
            "respects_received",
            "policy_accepted",
        ]

    def get_rating_status(self, obj: User) -> str:
        return rating_status_label(obj.rating_current)

    def get_policy_accepted(self, obj: User) -> bool:
        from apps.accounts.policy_views import has_accepted_current

        return has_accepted_current(obj)

    def get_path_reached(self, obj: User) -> list[str]:
        return path_reached(obj)

    def get_applied_items(self, obj: User) -> dict:
        return applied_purchases(obj)

    def get_duel_wins(self, obj: User) -> int:
        return duel_wins(obj)

    def get_respects_received(self, obj: User) -> int:
        return respects_received_count(obj)


class PublicProfileSerializer(serializers.ModelSerializer):
    track = serializers.CharField(source="track.name", read_only=True)
    squad = serializers.CharField(source="squad.name", read_only=True)
    rating_zone = serializers.SerializerMethodField()
    rating_current = serializers.SerializerMethodField()
    path_reached = serializers.SerializerMethodField()
    applied_items = serializers.SerializerMethodField()
    # Профиль показывает «Побед в дуэлях» — раньше поля не существовало,
    # и в интерфейсе всегда было пусто.
    duel_wins = serializers.SerializerMethodField()
    respects_received = serializers.SerializerMethodField()
    # п. 11.1: статус другого студента виден авторизованным, монеты — нет.
    rating_status = serializers.SerializerMethodField()
    # Раньше чужой профиль показывал только ник и карточку: статистику,
    # нашивки и диаграмму характеристик сервер для него не отдавал вовсе.
    quests_completed = serializers.SerializerMethodField()
    badges = serializers.SerializerMethodField()
    characteristics = serializers.SerializerMethodField()

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
            "rating_status",
            "rating_current",
            "path_reached",
            "applied_items",
            "duel_wins",
            "respects_received",
            "quests_completed",
            "badges",
            "characteristics",
        ]

    def get_quests_completed(self, obj: User) -> int:
        return obj.quest_progress.filter(is_completed=True).count()

    def get_badges(self, obj: User) -> list[dict]:
        rows = obj.badges.select_related("badge").order_by("-is_pinned", "-acquired_at")
        return PublicUserBadgeSerializer(rows, many=True).data

    def get_characteristics(self, obj: User) -> list[dict]:
        return characteristics_payload(obj)

    def get_duel_wins(self, obj: User) -> int:
        return duel_wins(obj)

    def get_respects_received(self, obj: User) -> int:
        return respects_received_count(obj)

    def get_path_reached(self, obj: User) -> list[str]:
        return path_reached(obj)

    def get_applied_items(self, obj: User) -> dict:
        return applied_purchases(obj)

    def get_rating_zone(self, obj: User) -> str:
        # Пороги живут в одном месте — apps.progress.services.rating_zones.
        return rating_zone(obj.rating_current)

    def get_rating_status(self, obj: User) -> str:
        return rating_status_label(obj.rating_current)

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


class AgentSearchSerializer(serializers.ModelSerializer):
    """Краткая карточка студента для подсказок поиска."""

    squad = serializers.CharField(source="squad.name", read_only=True, default="")
    track = serializers.CharField(source="track.name", read_only=True, default="")
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["username", "callsign", "full_name", "avatar", "squad", "track", "rating_current"]

    def get_full_name(self, obj: User) -> str:
        return f"{obj.last_name} {obj.first_name}".strip()
