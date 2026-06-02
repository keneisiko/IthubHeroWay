from django.conf import settings
from django.db import models


class Respect(models.Model):
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="От кого",
        on_delete=models.CASCADE,
        related_name="respects_given",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Кому",
        on_delete=models.CASCADE,
        related_name="respects_received",
    )
    message = models.CharField("Сообщение", max_length=255, blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Респект"
        verbose_name_plural = "Респекты"
        indexes = [
            models.Index(fields=["to_user", "-created_at"]),
        ]


class DuelStatus(models.TextChoices):
    PENDING = "pending", "Ожидает"
    ACCEPTED = "accepted", "Принят"
    REJECTED = "rejected", "Отклонён"


class Duel(models.Model):
    challenger = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Инициатор",
        on_delete=models.CASCADE,
        related_name="duels_started",
    )
    opponent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Соперник",
        on_delete=models.CASCADE,
        related_name="duels_received",
    )
    status = models.CharField(
        "Статус", max_length=16, choices=DuelStatus.choices, default=DuelStatus.PENDING
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    resolved_at = models.DateTimeField("Завершён", null=True, blank=True)

    class Meta:
        verbose_name = "Дуэль"
        verbose_name_plural = "Дуэли"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
        ]


class Mentorship(models.Model):
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Наставник",
        on_delete=models.CASCADE,
        related_name="mentees",
    )
    mentee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Подопечный",
        on_delete=models.CASCADE,
        related_name="mentors",
    )
    started_at = models.DateTimeField("Начало", auto_now_add=True)
    ended_at = models.DateTimeField("Окончание", null=True, blank=True)

    class Meta:
        verbose_name = "Наставничество"
        verbose_name_plural = "Наставничества"
        unique_together = ("mentor", "mentee")
        indexes = [
            models.Index(fields=["mentor", "mentee"]),
        ]
