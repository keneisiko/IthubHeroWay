from django.conf import settings
from django.db import models


class TelegramAccountLink(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="telegram_link")
    telegram_user_id = models.BigIntegerField(unique=True, db_index=True)
    telegram_username = models.CharField(max_length=255, blank=True)
    telegram_chat_id = models.BigIntegerField(db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["telegram_user_id", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.telegram_user_id}"


class ExternalEvent(models.Model):
    source = models.CharField(max_length=32, db_index=True)
    external_event_id = models.CharField(max_length=128)
    payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "external_event_id"], name="uniq_external_event_per_source"),
        ]
        indexes = [
            models.Index(fields=["source", "-processed_at"]),
        ]


class LXPSnapshot(models.Model):
    """Снимок данных из LXP на определённую дату."""

    date = models.DateField(unique=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"LXPSnapshot({self.date})"


class HikEvent(models.Model):
    """Сырое событие доступа из HikCentral / Hik-Connect."""

    event_id = models.CharField(max_length=128, unique=True, db_index=True)
    student_code = models.CharField(max_length=100, blank=True)
    event_time = models.DateTimeField()
    event_type = models.CharField(max_length=50, blank=True)
    door_name = models.CharField(max_length=200, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-event_time"]
        indexes = [
            models.Index(fields=["student_code", "event_time"]),
            models.Index(fields=["processed", "event_time"]),
        ]

    def __str__(self) -> str:
        return f"Hik({self.student_code}:{self.event_id})"

