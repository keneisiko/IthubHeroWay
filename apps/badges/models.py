from django.conf import settings
from django.db import models


class BadgeCategory(models.TextChoices):
    PROGRESS = "progress", "Progress"
    SOCIAL = "social", "Social"
    ACADEMIC = "academic", "Academic"
    SPECIAL = "special", "Special"


class BadgeRarity(models.TextChoices):
    COMMON = "common", "Common"
    RARE = "rare", "Rare"
    EPIC = "epic", "Epic"
    LEGENDARY = "legendary", "Legendary"


class Badge(models.Model):
    code = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=32, choices=BadgeCategory.choices, default=BadgeCategory.PROGRESS)
    rarity = models.CharField(max_length=16, choices=BadgeRarity.choices, default=BadgeRarity.COMMON)
    condition = models.JSONField(default=dict, blank=True)
    reward_coins = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "category"]),
        ]

    def __str__(self) -> str:
        return f"{self.code}: {self.title}"


class UserBadge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="awarded_users")
    acquired_at = models.DateTimeField(auto_now_add=True)
    is_pinned = models.BooleanField(default=False)
    source = models.CharField(max_length=64, blank=True)

    class Meta:
        unique_together = ("user", "badge")
        indexes = [
            models.Index(fields=["user", "-acquired_at"]),
            models.Index(fields=["user", "is_pinned"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.badge_id}"

