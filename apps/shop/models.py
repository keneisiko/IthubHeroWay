from django.conf import settings
from django.db import models


class ShopItemType(models.TextChoices):
    COSMETIC = "cosmetic", "Cosmetic"
    BOOST = "boost", "Boost"
    SERVICE = "service", "Service"
    OTHER = "other", "Other"


class ShopItem(models.Model):
    code = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    item_type = models.CharField(max_length=16, choices=ShopItemType.choices, default=ShopItemType.OTHER)
    price_coins = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    available_from = models.DateTimeField(null=True, blank=True)
    available_to = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "item_type"]),
            models.Index(fields=["available_from", "available_to"]),
        ]

    def __str__(self) -> str:
        return f"{self.code}: {self.title}"


class Purchase(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purchases")
    item = models.ForeignKey(ShopItem, on_delete=models.PROTECT, related_name="purchases")
    coins_spent = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.item_id} (-{self.coins_spent})"

