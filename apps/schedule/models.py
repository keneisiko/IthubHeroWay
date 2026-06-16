from django.db import models


class DayOfWeek(models.IntegerChoices):
    MONDAY = 0, "Понедельник"
    TUESDAY = 1, "Вторник"
    WEDNESDAY = 2, "Среда"
    THURSDAY = 3, "Четверг"
    FRIDAY = 4, "Пятница"
    SATURDAY = 5, "Суббота"
    SUNDAY = 6, "Воскресенье"


class Schedule(models.Model):
    """Расписание пар для отряда (для расчёта опозданий по Hik)."""

    squad = models.ForeignKey(
        "accounts.Squad",
        verbose_name="Отряд",
        on_delete=models.CASCADE,
        related_name="schedule_slots",
    )
    day_of_week = models.IntegerField("День недели", choices=DayOfWeek.choices)
    start_time = models.TimeField("Начало")
    end_time = models.TimeField("Окончание")
    discipline = models.CharField("Дисциплина", max_length=200, blank=True)
    is_active = models.BooleanField("Активно", default=True)

    class Meta:
        verbose_name = "Слот расписания"
        verbose_name_plural = "Расписание"
        constraints = [
            models.UniqueConstraint(
                fields=["squad", "day_of_week", "start_time"],
                name="uniq_schedule_squad_day_start",
            ),
        ]
        ordering = ["day_of_week", "start_time"]

    def __str__(self) -> str:
        return f"{self.squad_id} {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"
