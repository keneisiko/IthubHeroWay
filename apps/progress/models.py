from django.conf import settings
from django.db import models


class RatingChangeSource(models.TextChoices):
    QUEST = "quest", "Quest"
    BADGE = "badge", "Badge"
    SHOP = "shop", "Shop"
    SOCIAL = "social", "Social"
    MANUAL = "manual", "Manual"
    SYSTEM = "system", "System"


class RatingLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rating_logs")
    value_before = models.IntegerField()
    value_after = models.IntegerField()
    delta = models.IntegerField()
    source = models.CharField(max_length=16, choices=RatingChangeSource.choices, default=RatingChangeSource.SYSTEM)
    source_id = models.CharField(max_length=64, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.delta} ({self.source})"


class Characteristic(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="characteristics")
    pillar = models.CharField(max_length=32, db_index=True)
    current = models.FloatField(default=0)
    peak = models.FloatField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "pillar"], name="uniq_characteristic_per_user_pillar"),
        ]


class CharacteristicHistory(models.Model):
    characteristic = models.ForeignKey(
        Characteristic, on_delete=models.CASCADE, related_name="history_entries"
    )
    value = models.FloatField()
    formula_version = models.CharField(max_length=32, default="v1")
    created_at = models.DateTimeField(auto_now_add=True)

