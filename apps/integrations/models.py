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

    # Ниже — денормализация того, что раньше жило только внутри payload.
    # Из-за этого выборки «события пользователя за день» приходилось делать
    # полным перебором таблицы в Python: верификаторы квестов проходили по всем
    # событиям Hik для каждого пользователя и каждого дня.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="external_events",
    )
    event_date = models.DateField("Дата события", null=True, blank=True)
    event_type = models.CharField("Тип события", max_length=32, blank=True)

    class Meta:
        verbose_name = "Внешнее событие"
        verbose_name_plural = "Внешние события"
        constraints = [
            models.UniqueConstraint(fields=["source", "external_event_id"], name="uniq_external_event_per_source"),
        ]
        indexes = [
            models.Index(fields=["source", "-processed_at"]),
            models.Index(fields=["user", "event_date"]),
            models.Index(fields=["source", "event_type", "event_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.source}:{self.external_event_id}"

    def save(self, *args, **kwargs):
        """Держать колонки согласованными с payload.

        Колонки — денормализация payload ради индексов. Заполнять их вручную
        в каждом месте создания события ненадёжно: часть путей о них не знает
        (вебхук YouGile, импорт из LXP, фикстуры тестов), и тогда событие
        перестаёт находиться выборками по пользователю и дате.
        """
        payload = self.payload if isinstance(self.payload, dict) else {}

        if self.user_id is None:
            user_id = payload.get("user_id")
            if isinstance(user_id, int):
                self.user_id = user_id

        if not self.event_type:
            self.event_type = str(payload.get("event_type") or "")[:32]

        if self.event_date is None:
            self.event_date = self._event_date_from_payload(payload)

        super().save(*args, **kwargs)

    @staticmethod
    def _event_date_from_payload(payload: dict):
        from datetime import datetime

        from django.utils import timezone as dj_timezone

        raw = payload.get("event_time")
        if not isinstance(raw, str) or not raw:
            return None
        try:
            moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dj_timezone.is_naive(moment):
            moment = dj_timezone.make_aware(moment, dj_timezone.get_current_timezone())
        # Дата — в часовом поясе проекта: по ней сверяются расписание и опоздания.
        return dj_timezone.localtime(moment).date()


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


class HikSnapshot(models.Model):
    """Снимок проходов Hik-Connect / HikCentral на дату (ручной импорт или экспорт)."""

    date = models.DateField("Дата", unique=True)
    data = models.JSONField("Данные")
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Снимок Hik"
        verbose_name_plural = "Снимки Hik"
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"Снимок Hik ({self.date})"


class HikImportMode(models.TextChoices):
    WEB_API = "web_api", "Портал (HTTP)"
    BROWSER = "browser", "Портал (XLSX через браузер)"
    API = "api", "HikCentral OpenAPI"
    SNAPSHOT = "snapshot", "Ручной снимок"
    MANUAL = "manual", "Ручная загрузка файла"


class HikImportStatus(models.TextChoices):
    SUCCESS = "success", "Успешно"
    EMPTY = "empty", "Нет записей"
    ERROR = "error", "Ошибка"


class HikImportRun(models.Model):
    """Журнал попыток забрать проходы из Hik.

    Без него понять, работает ли интеграция, можно было только чтением логов
    контейнера: задача возвращала строку с нулями и считалась успешной
    одинаково и когда данных нет, и когда всё сломалось.
    """

    mode = models.CharField("Режим", max_length=16, choices=HikImportMode.choices, db_index=True)
    status = models.CharField("Статус", max_length=16, choices=HikImportStatus.choices, db_index=True)
    date_from = models.DateField("Период с")
    date_to = models.DateField("Период по")
    records_fetched = models.PositiveIntegerField("Получено записей", default=0)
    events_created = models.PositiveIntegerField("Новых событий", default=0)
    external_created = models.PositiveIntegerField("Создано ExternalEvent", default=0)
    users_unmatched = models.PositiveIntegerField("Без привязки к пользователю", default=0)
    relogin_used = models.BooleanField("Потребовался повторный вход", default=False)
    duration_ms = models.PositiveIntegerField("Длительность, мс", default=0)
    error = models.TextField("Ошибка", blank=True)
    started_at = models.DateTimeField("Начало", auto_now_add=True)

    class Meta:
        verbose_name = "Запуск импорта Hik"
        verbose_name_plural = "Запуски импорта Hik"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["-started_at"]),
            models.Index(fields=["status", "-started_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_mode_display()} {self.date_from}..{self.date_to}: {self.status}"


class HikEvent(models.Model):
    """Сырое событие доступа из HikCentral / Hik-Connect."""

    event_id = models.CharField("ID события", max_length=128, unique=True, db_index=True)
    student_code = models.CharField("Код студента", max_length=100, blank=True)
    event_time = models.DateTimeField("Время")
    event_type = models.CharField("Тип", max_length=50, blank=True)
    door_name = models.CharField("Турникет", max_length=200, blank=True)
    raw_data = models.JSONField("Сырые данные", default=dict, blank=True)
    processed = models.BooleanField("Обработано", default=False, db_index=True)
    # Событие, на котором обработчик падает, раньше не помечалось обработанным
    # и перечитывалось на каждом прогоне вечно, занимая место в пачке и снова
    # порождая ошибку. Счётчик позволяет отправить такое событие в карантин.
    process_attempts = models.PositiveSmallIntegerField("Попыток обработки", default=0)
    last_error = models.TextField("Последняя ошибка", blank=True)
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
