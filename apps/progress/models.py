from decimal import Decimal

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
    # Источники по Положению: учебная неделя (разделы 3), регулярные роли (4),
    # мероприятия (5), олимпиады (6), проекты (7), списания (9).
    ACADEMIC = "academic", "Учебная неделя"
    ROLE = "role", "Регулярная роль"
    EVENT = "event", "Мероприятие"
    OLYMPIAD = "olympiad", "Олимпиада"
    PROJECT = "project", "Проект"
    PENALTY = "penalty", "Списание"
    # Монеты за удержание топа рейтинга (apps.progress.services.king_of_hill).
    KING = "king", "Царь горы"
    CORRECTION = "correction", "Исправление"


class RatingLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="rating_logs",
    )
    value_before = models.DecimalField("Было", max_digits=10, decimal_places=2)
    value_after = models.DecimalField("Стало", max_digits=10, decimal_places=2)
    delta = models.DecimalField("Изменение", max_digits=10, decimal_places=2)
    # Монеты живут в той же записи, а не в отдельном журнале: по Положению
    # каждое начисление даёт и рейтинг, и монеты одним основанием, и история
    # (п. 10.1) должна показывать их вместе.
    coins_delta = models.DecimalField(
        "Монеты", max_digits=10, decimal_places=2, default=Decimal("0")
    )
    source = models.CharField(
        "Источник", max_length=16, choices=RatingChangeSource.choices, default=RatingChangeSource.SYSTEM
    )
    source_id = models.CharField("ID источника", max_length=64, blank=True)
    reason = models.CharField("Причина", max_length=255, blank=True)
    # п. 10.1: студент видит, кто подтвердил начисление. Пусто у расчётных
    # начислений — там подтверждает не человек, а данные LXP.
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Подтвердил",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_rating_logs",
    )
    period_key = models.CharField(
        "Расчётный период",
        max_length=16,
        blank=True,
        db_index=True,
        help_text="Неделя вида 2026-W43: один период не оплачивается повторно (п. 2.4).",
    )
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


class LessonAttendanceStatus(models.TextChoices):
    PRESENT = "present", "Был"
    ONLINE = "online", "Был онлайн"
    MISSED = "missed", "Пропустил"


class LessonAttendance(models.Model):
    """Отметка посещения конкретного занятия из LXP.

    Раньше посещаемость приходила одним числом за семестр: по нему нельзя
    сказать, был ли студент на этой неделе, и «80%» одинаково выглядели
    у того, кто перестал ходить вчера, и у того, кто пропускал в сентябре.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Студент",
        on_delete=models.CASCADE,
        related_name="lesson_attendance",
    )
    lxp_class_id = models.CharField("ID занятия в LXP", max_length=64, db_index=True)
    lesson_date = models.DateField("Дата занятия", db_index=True)
    starts_at = models.TimeField("Начало", null=True, blank=True)
    discipline = models.CharField("Дисциплина", max_length=255, blank=True)
    status = models.CharField(
        "Отметка", max_length=16, choices=LessonAttendanceStatus.choices, db_index=True
    )
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "Посещение занятия"
        verbose_name_plural = "Посещения занятий"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lxp_class_id"], name="uniq_lesson_attendance_user_class"
            ),
        ]
        indexes = [models.Index(fields=["user", "lesson_date"])]
        ordering = ["-lesson_date", "starts_at"]

    def __str__(self) -> str:
        return f"{self.user_id} {self.lesson_date} {self.get_status_display()}"


class StudentRoleKind(models.TextChoices):
    """Регулярные роли студентов из раздела 4 Положения."""

    CURATOR = "curator", "Куратор"
    TEACHER = "teacher", "Преподаватель"
    TECH = "tech", "Технический специалист"
    GROUP_LEAD = "group_lead", "Тимлид учебной группы"
    COUNCIL_LEAD = "council_lead", "Тимлид студенческого совета"
    CLUB_LEAD = "club_lead", "Руководитель клуба"
    VOLUNTEER_LEAD = "volunteer_lead", "Руководитель волонтёрского корпуса"


class StudentRoleAssignment(models.Model):
    """Действующий подтверждённый статус студента (п. 4.1-4.2).

    Ответственный фиксирует начало и окончание статуса. Хранится период, а не
    флаг «есть роль»: за неполную неделю начисление пропорционально числу
    учебных дней действия роли, и без дат его не посчитать.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Студент",
        on_delete=models.CASCADE,
        related_name="student_roles",
    )
    kind = models.CharField("Роль", max_length=32, choices=StudentRoleKind.choices, db_index=True)
    started_on = models.DateField("Действует с", db_index=True)
    ended_on = models.DateField("Действует по", null=True, blank=True, db_index=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Подтвердил",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_student_roles",
    )
    note = models.CharField("Примечание", max_length=255, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Роль студента"
        verbose_name_plural = "Роли студентов"
        indexes = [models.Index(fields=["user", "kind", "started_on"])]
        ordering = ["-started_on"]

    def __str__(self) -> str:
        end = self.ended_on.isoformat() if self.ended_on else "…"
        return f"{self.user_id} {self.kind} {self.started_on}–{end}"

    def is_active_on(self, day) -> bool:
        if day < self.started_on:
            return False
        return self.ended_on is None or day <= self.ended_on


class PolozhenieAwardKind(models.TextChoices):
    """Разовые начисления по разделам 5-7 Положения."""

    EVENT = "event", "Мероприятие"
    OLYMPIAD = "olympiad", "Олимпиада"
    PROJECT = "project", "Проект"


class PolozhenieAward(models.Model):
    """Подтверждённое разовое начисление: мероприятие, олимпиада, проект.

    Отдельная запись, а не только строка журнала: по Положению за одно и то же
    мероприятие применяется одна высшая роль (п. 5.2), а победа на олимпиаде
    начисляется вместо участия с доплатой разницы (п. 6.3). И то и другое
    требует помнить, что по этому мероприятию студенту уже начислено.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Студент",
        on_delete=models.CASCADE,
        related_name="polozhenie_awards",
    )
    kind = models.CharField("Вид", max_length=16, choices=PolozhenieAwardKind.choices, db_index=True)
    # Ключ мероприятия: по нему Положение запрещает платить дважды за одно
    # и то же. Для проектов это код задания, для олимпиад — код олимпиады.
    activity_key = models.CharField("Ключ активности", max_length=64, db_index=True)
    title = models.CharField("Название", max_length=255, blank=True)
    level = models.CharField("Уровень", max_length=16, blank=True)
    role = models.CharField("Роль или результат", max_length=16, blank=True)
    happened_on = models.DateField("Дата", db_index=True)
    rating_granted = models.DecimalField(
        "Начислено рейтинга", max_digits=10, decimal_places=2, default=Decimal("0")
    )
    coins_granted = models.DecimalField(
        "Начислено монет", max_digits=10, decimal_places=2, default=Decimal("0")
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Подтвердил",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_polozhenie_awards",
    )
    note = models.CharField("Примечание", max_length=255, blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Начисление по Положению"
        verbose_name_plural = "Начисления по Положению"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "kind", "activity_key"],
                name="uniq_polozhenie_award_per_activity",
            ),
        ]
        indexes = [models.Index(fields=["user", "-happened_on"])]
        ordering = ["-happened_on"]

    def __str__(self) -> str:
        return f"{self.user_id} {self.kind}:{self.activity_key} ({self.role}/{self.level})"
