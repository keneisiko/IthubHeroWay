from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    AGENT = "agent", "Агент"
    CURATOR = "curator", "Куратор"
    TUTOR = "tutor", "Тьютор"
    ADMIN = "admin", "Админ"
    HQ = "hq", "Штаб"


class Track(models.Model):
    code = models.CharField("Код", max_length=50, unique=True)
    name = models.CharField("Название", max_length=255)

    class Meta:
        verbose_name = "Направление"
        verbose_name_plural = "Направления"

    def __str__(self) -> str:
        return self.name


class Squad(models.Model):
    code = models.CharField("Код", max_length=50, unique=True, db_index=True)
    name = models.CharField("Название", max_length=255)
    course = models.PositiveSmallIntegerField("Курс", null=True, blank=True)
    capacity = models.PositiveSmallIntegerField("Вместимость", null=True, blank=True)
    # Проставляется импортом группы: по нему ночные задачи знают, откуда
    # брать расписание и отметки посещения, без ручного списка в настройках.
    lxp_group_id = models.CharField("ID учебной группы LXP", max_length=64, blank=True, db_index=True)

    class Meta:
        verbose_name = "Отряд"
        verbose_name_plural = "Отряды"

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    callsign = models.CharField("Позывной", max_length=50, unique=True, db_index=True)
    avatar = models.ImageField("Аватар", upload_to="avatars/", null=True, blank=True)
    track = models.ForeignKey(
        Track,
        verbose_name="Направление",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )
    squad = models.ForeignKey(
        Squad,
        verbose_name="Отряд",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )
    role = models.CharField("Роль", max_length=16, choices=Role.choices, default=Role.AGENT)
    # п. 2.4 Положения: рейтинг и монеты учитываются до двух знаков после
    # запятой. Недельная формула даёт дробные значения (17 × 0,8 = 13,6),
    # и округление до целого съедало бы до половины балла каждую неделю.
    coins_balance = models.DecimalField(
        "Баланс монет", max_digits=10, decimal_places=2, default=Decimal("0")
    )
    status = models.CharField("Статус", max_length=64, blank=True)
    level = models.PositiveIntegerField("Уровень", default=1)
    # п. 2.2: рейтинг на начало сезона равен нулю. п. 1.3: верхней границы нет.
    rating_current = models.DecimalField(
        "Текущий рейтинг",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        db_index=True,
    )
    unclosed_ct_count = models.PositiveSmallIntegerField("Незакрытых КТ", default=0)
    lxp_user_id = models.CharField(
        "ID в LXP",
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Идентификатор пользователя в LXP (GraphQL user.id), для связи со снимком",
    )
    hik_card_code = models.CharField(
        "Код карты Hik",
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Код карты / personCode для HikCentral (привязка проходов к пользователю)",
    )
    hik_person_id = models.CharField(  # noqa: DJ001
        "ID лица Hik",
        max_length=100,
        blank=True,
        # NULL, а не пустая строка: «лица нет в Hik» и «лицо есть, идентификатор
        # пустой» — разные состояния, а соседний hik_card_code обязан быть
        # nullable из-за unique. Семантику держим одинаковой.
        null=True,
        db_index=True,
        help_text="Идентификатор лица в HikCentral при наличии",
    )

    class Meta(AbstractUser.Meta):
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        indexes = [
            models.Index(fields=["rating_current"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self) -> str:
        return self.username


class PolicyAcceptance(models.Model):
    """Принятие Положения студентом (п. 2.1).

    Студент активирует профиль входом с учебным логином «после ознакомления
    и принятия настоящего Положения». Храним версию: при смене редакции
    (п. 12.3 — изменения доводятся до применения) согласие запрашивается
    заново, а старое остаётся в истории.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="policy_acceptances",
    )
    version = models.CharField("Версия Положения", max_length=16, db_index=True)
    accepted_at = models.DateTimeField("Принято", auto_now_add=True)

    class Meta:
        verbose_name = "Принятие Положения"
        verbose_name_plural = "Принятия Положения"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "version"], name="uniq_policy_acceptance_per_version"
            ),
        ]
        ordering = ["-accepted_at"]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.version}"
