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

