from django.conf import settings
from django.db import models


class RatingChangeSource(models.TextChoices):
    QUEST = "quest", "Квест"
    BADGE = "badge", "Значок"
    SHOP = "shop", "Магазин"
    SOCIAL = "social", "Социальное"
    MANUAL = "manual", "Вручную"
    SYSTEM = "system", "Система"


class RatingLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="rating_logs",
    )
    value_before = models.IntegerField("Было")
    value_after = models.IntegerField("Стало")
    delta = models.IntegerField("Изменение")
    source = models.CharField(
        "Источник", max_length=16, choices=RatingChangeSource.choices, default=RatingChangeSource.SYSTEM
    )
    source_id = models.CharField("ID источника", max_length=64, blank=True)
    reason = models.CharField("Причина", max_length=255, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Запись рейтинга"
        verbose_name_plural = "Журнал рейтинга"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.delta} ({self.source})"


class Characteristic(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="characteristics",
    )
    pillar = models.CharField("Опора", max_length=32, db_index=True)
    current = models.FloatField("Текущее значение", default=0)
    peak = models.FloatField("Пик", default=0)
    last_updated = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Характеристика"
        verbose_name_plural = "Характеристики"
        constraints = [
            models.UniqueConstraint(fields=["user", "pillar"], name="uniq_characteristic_per_user_pillar"),
        ]


class CharacteristicHistory(models.Model):
    characteristic = models.ForeignKey(
        Characteristic,
        verbose_name="Характеристика",
        on_delete=models.CASCADE,
        related_name="history_entries",
    )
    value = models.FloatField("Значение")
    formula_version = models.CharField("Версия формулы", max_length=32, default="v1")
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "История характеристики"
        verbose_name_plural = "История характеристик"


class UserStrike(models.Model):
    """Серии без пропусков и без опозданий для бонусов."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="strike",
    )
    attendance_strike = models.PositiveIntegerField("Дней без пропусков", default=0)
    late_strike = models.PositiveIntegerField("Дней без опозданий", default=0)
    last_attendance_date = models.DateField("Последний день посещаемости", null=True, blank=True)
    last_late_date = models.DateField("Последний день без опозданий", null=True, blank=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Серия студента"
        verbose_name_plural = "Серии студентов"

    def __str__(self) -> str:
        return f"{self.user_id}: att={self.attendance_strike} late={self.late_strike}"
