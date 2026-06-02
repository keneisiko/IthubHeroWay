from django.conf import settings
from django.db import models


class BadgeCategory(models.TextChoices):
    PROGRESS = "progress", "Прогресс"
    SOCIAL = "social", "Социальное"
    ACADEMIC = "academic", "Учёба"
    SPECIAL = "special", "Особый"


class BadgeRarity(models.TextChoices):
    COMMON = "common", "Обычный"
    RARE = "rare", "Редкий"
    EPIC = "epic", "Эпический"
    LEGENDARY = "legendary", "Легендарный"


class Badge(models.Model):
    code = models.CharField("Код", max_length=64, unique=True)
    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    category = models.CharField(
        "Категория", max_length=32, choices=BadgeCategory.choices, default=BadgeCategory.PROGRESS
    )
    rarity = models.CharField(
        "Редкость", max_length=16, choices=BadgeRarity.choices, default=BadgeRarity.COMMON
    )
    condition = models.JSONField("Условие", default=dict, blank=True)
    reward_coins = models.PositiveIntegerField("Награда (монеты)", default=0)
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Значок"
        verbose_name_plural = "Значки"
        indexes = [
            models.Index(fields=["is_active", "category"]),
        ]

    def __str__(self) -> str:
        return f"{self.code}: {self.title}"


class UserBadge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="badges",
    )
    badge = models.ForeignKey(
        Badge, verbose_name="Значок", on_delete=models.CASCADE, related_name="awarded_users"
    )
    acquired_at = models.DateTimeField("Получен", auto_now_add=True)
    is_pinned = models.BooleanField("Закреплён", default=False)
    source = models.CharField("Источник", max_length=64, blank=True)

    class Meta:
        verbose_name = "Значок пользователя"
        verbose_name_plural = "Значки пользователей"
        unique_together = ("user", "badge")
        indexes = [
            models.Index(fields=["user", "-acquired_at"]),
            models.Index(fields=["user", "is_pinned"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.badge_id}"
