from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    AGENT = "agent", "Агент"
    CURATOR = "curator", "Куратор"
    TUTOR = "tutor", "Тьютор"
    ADMIN = "admin", "Админ"
    HQ = "hq", "Штаб"


class Track(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


class Squad(models.Model):
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    # curator FK будет добавлен позже, когда появится User
    course = models.PositiveSmallIntegerField(null=True, blank=True)
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    callsign = models.CharField(max_length=50, unique=True, db_index=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    track = models.ForeignKey(
        Track, null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )
    squad = models.ForeignKey(
        Squad, null=True, blank=True, on_delete=models.SET_NULL, related_name="members"
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.AGENT)
    coins_balance = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=64, blank=True)
    level = models.PositiveIntegerField(default=1)
    rating_current = models.PositiveIntegerField(default=300, db_index=True)
    unclosed_ct_count = models.PositiveSmallIntegerField(default=0)
    lxp_user_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Идентификатор пользователя в LXP (GraphQL user.id), для связи со снимком",
    )
    hik_card_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Код карты / personCode для HikCentral (привязка проходов к пользователю)",
    )
    hik_person_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Идентификатор лица в HikCentral при наличии",
    )

    class Meta:
        indexes = [
            models.Index(fields=["rating_current"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self) -> str:
        return self.username

