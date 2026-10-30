from rest_framework import serializers

from .models import Badge, UserBadge


class BadgeSerializer(serializers.ModelSerializer):
    """Публичное представление значка.

    Поле `condition` намеренно не отдаётся: это правило выдачи награды,
    и клиенту знать точные пороги незачем — описание для студента живёт
    в `description`.
    """

    # Доля активированных студентов, у которых нашивка есть, — как редкость
    # достижений в Steam. Отдаётся только каталогом (там есть аннотация);
    # во вложенных нашивках профиля — null.
    owners_percent = serializers.SerializerMethodField()

    class Meta:
        model = Badge
        fields = [
            "id",
            "code",
            "title",
            "description",
            "category",
            "rarity",
            "reward_coins",
            "is_active",
            "owners_percent",
            "avatar_frame",
        ]

    def get_owners_percent(self, obj: Badge) -> float | None:
        owners = getattr(obj, "owners_count", None)
        total = self.context.get("students_total")
        if owners is None or not total:
            return None
        return round(owners / total * 100, 1)


class UserBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ["id", "badge", "acquired_at", "is_pinned", "source"]


class PublicUserBadgeSerializer(serializers.ModelSerializer):
    """Нашивка в чужом профиле — без `source`: там логин выдавшего сотрудника."""

    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ["id", "badge", "acquired_at", "is_pinned"]



class BadgeHolderSerializer(serializers.ModelSerializer):
    """Владелец нашивки в её карточке: кто и когда получил.

    Только то, что и так видно в рейтинге и профиле, — без точного
    рейтинга и без `source` (там логин выдавшего сотрудника).
    """

    username = serializers.CharField(source="user.username", read_only=True)
    callsign = serializers.CharField(source="user.callsign", read_only=True)
    avatar = serializers.ImageField(source="user.avatar", read_only=True)
    squad = serializers.CharField(source="user.squad.name", read_only=True, default="")
    avatar_frame = serializers.SerializerMethodField()

    class Meta:
        model = UserBadge
        fields = ["username", "callsign", "avatar", "avatar_frame", "squad", "acquired_at"]

    def get_avatar_frame(self, obj: UserBadge) -> str:
        from apps.accounts.frames import resolve_frame

        return resolve_frame(getattr(obj, "badge_frame", None), getattr(obj, "applied_cosmetic", None))
