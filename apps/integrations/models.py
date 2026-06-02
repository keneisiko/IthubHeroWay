from django.conf import settings
from django.db import models


class TelegramAccountLink(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="telegram_link",
    )
    telegram_user_id = models.BigIntegerField("Telegram ID", unique=True, db_index=True)
    telegram_username = models.CharField("Имя в Telegram", max_length=255, blank=True)
    telegram_chat_id = models.BigIntegerField("Chat ID", db_index=True)
    is_active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "Привязка Telegram"
        verbose_name_plural = "Привязки Telegram"
        indexes = [
            models.Index(fields=["telegram_user_id", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.telegram_user_id}"


class ExternalEvent(models.Model):
    source = models.CharField("Источник", max_length=32, db_index=True)
    external_event_id = models.CharField("Внешний ID", max_length=128)
    payload = models.JSONField("Данные", default=dict, blank=True)
    processed_at = models.DateTimeField("Обработано", auto_now_add=True)

    class Meta:
        verbose_name = "Внешнее событие"
        verbose_name_plural = "Внешние события"
        constraints = [
            models.UniqueConstraint(fields=["source", "external_event_id"], name="uniq_external_event_per_source"),
        ]
        indexes = [
            models.Index(fields=["source", "-processed_at"]),
        ]


class LXPSnapshot(models.Model):
    """Снимок данных из LXP на определённую дату."""

    date = models.DateField("Дата")
    data = models.JSONField("Данные")
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Снимок LXP"
        verbose_name_plural = "Снимки LXP"
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"Снимок LXP ({self.date})"


class HikEvent(models.Model):
    """Сырое событие доступа из HikCentral / Hik-Connect."""

    event_id = models.CharField("ID события", max_length=128, unique=True, db_index=True)
    student_code = models.CharField("Код студента", max_length=100, blank=True)
    event_time = models.DateTimeField("Время")
    event_type = models.CharField("Тип", max_length=50, blank=True)
    door_name = models.CharField("Турникет", max_length=200, blank=True)
    raw_data = models.JSONField("Сырые данные", default=dict, blank=True)
    processed = models.BooleanField("Обработано", default=False, db_index=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Событие Hik"
        verbose_name_plural = "События Hik"
        ordering = ["-event_time"]
        indexes = [
            models.Index(fields=["student_code", "event_time"]),
            models.Index(fields=["processed", "event_time"]),
        ]

    def __str__(self) -> str:
        return f"Hik({self.student_code}:{self.event_id})"
