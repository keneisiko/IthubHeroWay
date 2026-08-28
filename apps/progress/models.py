from django.conf import settings
from django.db import models


class RatingChangeSource(models.TextChoices):
    QUEST = "quest", "Квест"
    BADGE = "badge", "Значок"
    SHOP = "shop", "Магазин"
    SOCIAL = "social", "Социальное"
    # Мероприятия, олимпиады, волонтёрство, проекты — блок RATING_DRIVE.
    DRIVE = "drive", "Движ"
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

    def __str__(self) -> str:
        return f"{self.user_id}:{self.pillar}={self.current}"


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

    def __str__(self) -> str:
        return f"{self.characteristic_id}:{self.value} ({self.formula_version})"


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


class LXPTopicState(models.Model):
    """Состояние тем студента на момент последнего снимка LXP.

    Без него рейтинг приходилось считать от текущего состояния, и одна и та же
    незакрытая тема штрафовалась каждый день заново. Здесь хранится, что уже
    было учтено, поэтому начисление идёт за событие: тема закрылась — плюс,
    тема висит открытой дольше срока — минус один раз.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="lxp_topic_state",
    )
    # {"<дисциплина>:<тема>": {"closed": bool, "since": "YYYY-MM-DD", "penalized": bool}}
    topics = models.JSONField("Темы", default=dict, blank=True)
    last_snapshot_date = models.DateField("Последний учтённый снимок", null=True, blank=True)
    # Первый снимок только фиксирует состояние: начислять за темы, закрытые
    # до подключения системы, было бы выдачей рейтинга задним числом.
    baseline_done = models.BooleanField("База зафиксирована", default=False)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Состояние тем LXP"
        verbose_name_plural = "Состояния тем LXP"

    def __str__(self) -> str:
        return f"{self.user_id}: тем={len(self.topics or {})} на {self.last_snapshot_date}"


class CourseTopicNorm(models.Model):
    """Ожидаемое число тем за год по курсу — делитель годового бюджета.

    Курс с 60 темами и курс с 30 темами при одинаковой цене темы получали бы
    за год вдвое разный максимум. Здесь копится наблюдаемый максимум объёма
    по курсу, и цена одной темы считается от него.
    """

    course = models.PositiveSmallIntegerField("Курс", unique=True)
    expected_topics = models.PositiveIntegerField("Ожидаемое число тем", default=0)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Нормировка курса"
        verbose_name_plural = "Нормировки курсов"

    def __str__(self) -> str:
        return f"курс {self.course}: {self.expected_topics} тем"
