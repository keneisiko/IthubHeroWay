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
    coins_balance = models.PositiveIntegerField("Баланс монет", default=0)
    status = models.CharField("Статус", max_length=64, blank=True)
    level = models.PositiveIntegerField("Уровень", default=1)
    rating_current = models.PositiveIntegerField("Текущий рейтинг", default=300, db_index=True)
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
    hik_person_id = models.CharField(
        "ID лица Hik",
        max_length=100,
        blank=True,
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
