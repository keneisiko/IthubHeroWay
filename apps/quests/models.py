from django.conf import settings
from django.db import models


class QuestType(models.TextChoices):
    DAILY = "daily", "Ежедневный"
    WEEKLY = "weekly", "Еженедельный"
    EVENT = "event", "Событийный"
    LONG = "long", "Долгий"
    SELF_REPORT = "self_report", "Самоотчёт"
    MIXED = "mixed", "Смешанный"


class Quest(models.Model):
    code = models.CharField("Код", max_length=64, unique=True)
    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    quest_type = models.CharField(
        "Тип квеста", max_length=16, choices=QuestType.choices, default=QuestType.DAILY
    )
    reward_coins = models.PositiveIntegerField("Награда (монеты)", default=0)
    reward_rating_delta = models.IntegerField("Награда (рейтинг)", default=0)
    conditions = models.JSONField("Условия", default=dict, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    start_at = models.DateTimeField("Начало", null=True, blank=True)
    end_at = models.DateTimeField("Окончание", null=True, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Квест"
        verbose_name_plural = "Квесты"
        indexes = [
            models.Index(fields=["is_active", "quest_type"]),
            models.Index(fields=["start_at", "end_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.code}: {self.title}"


class UserQuestProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="quest_progress",
    )
    quest = models.ForeignKey(
        Quest, verbose_name="Квест", on_delete=models.CASCADE, related_name="user_progress"
    )
    progress_value = models.FloatField("Прогресс", default=0)
    is_completed = models.BooleanField("Выполнен", default=False)
    completed_at = models.DateTimeField("Дата выполнения", null=True, blank=True)
    proof_payload = models.JSONField("Данные подтверждения", default=dict, blank=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Прогресс по квесту"
        verbose_name_plural = "Прогресс по квестам"
        unique_together = ("user", "quest")
        indexes = [
            models.Index(fields=["user", "is_completed"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.quest_id}:{'done' if self.is_completed else 'active'}"


class QuestRewardTransaction(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="quest_rewards",
    )
    quest = models.ForeignKey(
        Quest, verbose_name="Квест", on_delete=models.CASCADE, related_name="reward_transactions"
    )
    progress = models.ForeignKey(
        UserQuestProgress,
        verbose_name="Прогресс",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reward_transactions",
    )
    coins_delta = models.IntegerField("Монеты", default=0)
    rating_delta = models.IntegerField("Рейтинг", default=0)
    granted_at = models.DateTimeField("Начислено", auto_now_add=True)

    class Meta:
        verbose_name = "Награда за квест"
        verbose_name_plural = "Награды за квесты"
        unique_together = ("user", "quest")
        indexes = [
            models.Index(fields=["user", "-granted_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.quest_id} (+{self.coins_delta}c, +{self.rating_delta}r)"


class SeasonalEvent(models.Model):
    code = models.CharField("Код", max_length=64, unique=True)
    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    progress_percent = models.PositiveSmallIntegerField("Прогресс, %", default=0)
    is_active = models.BooleanField("Активна", default=False)
    started_at = models.DateTimeField("Начало", null=True, blank=True)
    ended_at = models.DateTimeField("Окончание", null=True, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Сезонная операция"
        verbose_name_plural = "Сезонные операции"
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["started_at", "ended_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.code}: {self.title}"


class SquadLeaderboardSnapshot(models.Model):
    squad = models.ForeignKey(
        "accounts.Squad",
        verbose_name="Отряд",
        on_delete=models.CASCADE,
        related_name="leaderboard_snapshots",
    )
    avg_rating = models.FloatField("Средний рейтинг", default=0)
    agents_count = models.PositiveIntegerField("Число агентов", default=0)
    captured_at = models.DateTimeField("Снимок", auto_now_add=True)

    class Meta:
        verbose_name = "Снимок рейтинга отряда"
        verbose_name_plural = "Снимки рейтинга отрядов"
        indexes = [
            models.Index(fields=["-captured_at"]),
            models.Index(fields=["squad", "-captured_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.squad_id}:{self.avg_rating}"


class SelfReportProofStatus(models.TextChoices):
    PENDING = "pending", "На проверке"
    APPROVED = "approved", "Одобрен"
    REJECTED = "rejected", "Отклонён"


class SelfReportProof(models.Model):
    quest = models.ForeignKey(
        Quest, verbose_name="Квест", on_delete=models.CASCADE, related_name="self_report_proofs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="self_report_proofs",
    )
    quest_progress = models.OneToOneField(
        UserQuestProgress,
        verbose_name="Прогресс",
        on_delete=models.CASCADE,
        related_name="self_report_proof",
    )
    comment = models.TextField("Комментарий")
    status = models.CharField(
        "Статус",
        max_length=16,
        choices=SelfReportProofStatus.choices,
        default=SelfReportProofStatus.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Проверил",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="self_report_reviews",
    )
    reviewed_at = models.DateTimeField("Дата проверки", null=True, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Самоотчёт"
        verbose_name_plural = "Самоотчёты"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.quest_id}:{self.status}"
