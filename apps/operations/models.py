"""Настройки платформы, которые меняет персонал без разработчика.

До этой модели каждое из этих чисел было записано в коде или в `.env.prod`:
чтобы поменять дневной предел монет, нужны были коммит и выкатка, а чтобы
сдвинуть допуск опоздания — SSH и перезапуск контейнеров.

Сюда вынесены только операционные ручки. Тарифы Положения остаются в коде
(`hero_path/settings/polozhenie.py`): смена тарифа — это новая редакция
нормативного документа, а не настройка, и посреди недели она дала бы части
студентов начисление по старому тарифу, части — по новому.
"""

from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class CtScope(models.TextChoices):
    """Какие КТ считать актуальными в недельном расчёте (раздел 3 Положения)."""

    DEFERRED = "deferred", "Отложено: компонент КТ не начисляется, копится"
    DECIDED = "decided", "Только сданные и не сданные темы"
    DECIDED_WITH_PENDING = "decided_with_pending", "Плюс темы на проверке"


class PlatformSettings(models.Model):
    """Одна строка на всю платформу (pk=1)."""

    SINGLETON_PK = 1

    # --- выключатель начислений ----------------------------------------------
    # Меняется не полем формы, а кнопкой на странице настроек: дата старта
    # ставится сама, и забыть или перепутать её нельзя.
    accruals_enabled = models.BooleanField(
        "Начисления включены",
        default=False,
        help_text=(
            "Пока выключено, рейтинг, монеты, квесты, нашивки, дуэли и респекты ничего не "
            "начисляют. Переключается кнопкой «Включить начисления» на этой странице."
        ),
    )
    accruals_started_on = models.DateField(
        "Начисления стартовали",
        null=True,
        blank=True,
        help_text=(
            "День последнего включения. Сезон считается с него: данные за прошлые дни "
            "не оплачиваются. При выключении не стирается."
        ),
    )

    # --- монеты и квесты -------------------------------------------------
    max_daily_coins = models.PositiveIntegerField(
        "Дневной предел монет",
        help_text=(
            "Сколько монет студент может получить за день из квестов и нашивок. "
            "Начисления по Положению (разделы 3–7) через предел не проходят."
        ),
        validators=[MinValueValidator(1), MaxValueValidator(10_000)],
    )
    max_daily_self_reports = models.PositiveIntegerField(
        "Самоотчётов в день",
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )

    # --- отряды и соцмеханики ---------------------------------------------
    squad_weekly_bonus_percent = models.PositiveIntegerField(
        "Командный бонус: доля отряда, %",
        help_text="Какая доля отряда должна закрыть недельный квест, чтобы бонус получили все.",
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    squad_weekly_bonus_coins = models.PositiveIntegerField(
        "Командный бонус: монет каждому",
        validators=[MaxValueValidator(1_000)],
    )
    respect_weekly_limit = models.PositiveIntegerField(
        "Респектов в неделю от одного студента",
        validators=[MinValueValidator(1), MaxValueValidator(50)],
    )
    duel_bet = models.PositiveIntegerField(
        "Ставка в дуэли, монет", validators=[MinValueValidator(1), MaxValueValidator(1_000)]
    )
    duel_duration_days = models.PositiveIntegerField(
        "Длительность дуэли, дней", validators=[MinValueValidator(1), MaxValueValidator(60)]
    )
    duel_invite_ttl_days = models.PositiveIntegerField(
        "Вызов на дуэль ждёт ответа, дней",
        validators=[MinValueValidator(1), MaxValueValidator(30)],
    )
    duel_max_rating_diff = models.PositiveIntegerField(
        "Макс. разница рейтинга для дуэли",
        help_text="Нельзя вызвать соперника, чей рейтинг отличается сильнее.",
        validators=[MinValueValidator(1), MaxValueValidator(10_000)],
    )

    # --- посещаемость и успеваемость -----------------------------------------
    hik_late_grace_minutes = models.PositiveIntegerField(
        "Допуск опоздания, минут",
        help_text="Проход через турникет позже начала пары на это число минут ещё не опоздание.",
        validators=[MaxValueValidator(60)],
    )
    ct_scope = models.CharField(
        "Правило учёта КТ",
        max_length=32,
        choices=CtScope.choices,
        help_text=(
            "Пока колледж не выбрал правило, компонент КТ не начисляется и копится. "
            "После выбора недоплаченное начисляется командой accrue_week --since."
        ),
    )
    ct_min_actual = models.PositiveIntegerField(
        "Минимум актуальных КТ для расчёта",
        help_text="Если актуальных тем меньше, процент не считается — слишком мало данных.",
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    require_telegram_link_for_scoring = models.BooleanField(
        "Начислять только привязавшим Telegram",
        help_text=(
            "Выключено по Положению (п. 2.1–2.2): начисления идут всем студентам. "
            "Включать только для закрытых прогонов."
        ),
    )

    shop_pickup_info = models.TextField(
        "Где и когда забрать заказ",
        blank=True,
        default="",
        help_text="Кто выдаёт мерч и услуги, где и в какое время. Студент видит это в своих заказах.",
    )

    updated_at = models.DateTimeField("Изменено", auto_now=True)

    class Meta:
        verbose_name = "Настройки платформы"
        verbose_name_plural = "Настройки платформы"

    def __str__(self) -> str:
        return "Настройки платформы"

    def save(self, *args, **kwargs):
        # Строка одна: вторая создала бы вопрос «какая из них действует».
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)
        # Новое значение должно действовать сразу, а не через пять минут,
        # когда истечёт кеш: иначе сотрудник поменял бы предел, проверил —
        # и увидел старое поведение.
        from apps.operations.services.platform_settings import invalidate

        invalidate()
