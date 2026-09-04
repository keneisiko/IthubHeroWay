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

    def __str__(self) -> str:
        return f"{self.from_user_id} → {self.to_user_id}"


class DuelStatus(models.TextChoices):
    PENDING = "pending", "Ожидает"
    ACCEPTED = "accepted", "Принят"
    REJECTED = "rejected", "Отклонён"
    FINISHED = "finished", "Завершён"


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
    accepted_at = models.DateTimeField("Принят", null=True, blank=True)
    resolved_at = models.DateTimeField("Завершён", null=True, blank=True)
    # Итог считается по приросту рейтинга за время дуэли, поэтому стартовые
    # значения фиксируются в момент принятия вызова.
    challenger_rating_start = models.IntegerField("Рейтинг инициатора на старте", null=True, blank=True)
    opponent_rating_start = models.IntegerField("Рейтинг соперника на старте", null=True, blank=True)
    resolve_after = models.DateTimeField("Подводить итог после", null=True, blank=True)
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Победитель",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="duels_won",
    )
    bet_coins = models.PositiveIntegerField("Ставка (монеты)", default=0)

    class Meta:
        verbose_name = "Дуэль"
        verbose_name_plural = "Дуэли"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["status", "resolve_after"]),
        ]

    def __str__(self) -> str:
        return f"{self.challenger_id} vs {self.opponent_id} ({self.status})"


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
        constraints = [
            # Наставничество над самим собой давало монеты за «подопечного»
            # (MENTEE_WEEKLY_COINS) на ровном месте. Вьюха это отсекает, но
            # запись создаётся и из админки, и из команд — гарантия нужна в БД.
            models.CheckConstraint(
                condition=~models.Q(mentor=models.F("mentee")),
                name="social_mentorship_mentor_ne_mentee",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.mentor_id} → {self.mentee_id}"
