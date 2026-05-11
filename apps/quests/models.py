from django.conf import settings
from django.db import models


class QuestType(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    EVENT = "event", "Event"
    LONG = "long", "Long"


class Quest(models.Model):
    code = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    quest_type = models.CharField(max_length=16, choices=QuestType.choices, default=QuestType.DAILY)
    reward_coins = models.PositiveIntegerField(default=0)
    reward_rating_delta = models.IntegerField(default=0)
    conditions = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "quest_type"]),
            models.Index(fields=["start_at", "end_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.code}: {self.title}"


class UserQuestProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quest_progress")
    quest = models.ForeignKey(Quest, on_delete=models.CASCADE, related_name="user_progress")
    progress_value = models.FloatField(default=0)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    proof_payload = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "quest")
        indexes = [
            models.Index(fields=["user", "is_completed"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.quest_id}:{'done' if self.is_completed else 'active'}"


class QuestRewardTransaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quest_rewards")
    quest = models.ForeignKey(Quest, on_delete=models.CASCADE, related_name="reward_transactions")
    progress = models.ForeignKey(
        UserQuestProgress,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reward_transactions",
    )
    coins_delta = models.IntegerField(default=0)
    rating_delta = models.IntegerField(default=0)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "quest")
        indexes = [
            models.Index(fields=["user", "-granted_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.quest_id} (+{self.coins_delta}c, +{self.rating_delta}r)"

