from django.conf import settings
from django.db import models


class ShopItemType(models.TextChoices):
    COSMETIC = "cosmetic", "Косметика"
    BOOST = "boost", "Усиление"
    SERVICE = "service", "Услуга"
    OTHER = "other", "Прочее"


class ShopItemSlot(models.TextChoices):
    """Слот, который занимает предмет. Надеть можно по одному на слот."""

    AVATAR_FRAME = "avatar_frame", "Рамка аватара"
    BADGE_GLOW = "badge_glow", "Свечение значка"
    PROFILE_BANNER = "profile_banner", "Баннер профиля"
    BOOST = "boost", "Буст"


# Слоты, которые «надеваются». Буст не надевают: он тратится сам при награде за квест.
COSMETIC_SLOTS: tuple[str, ...] = (
    ShopItemSlot.AVATAR_FRAME,
    ShopItemSlot.BADGE_GLOW,
    ShopItemSlot.PROFILE_BANNER,
)


BOOST_QUEST_X2_CODE = "boost-quest-x2"


class ShopItem(models.Model):
    code = models.CharField("Код", max_length=64, unique=True)
    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    item_type = models.CharField(
        "Тип товара", max_length=16, choices=ShopItemType.choices, default=ShopItemType.OTHER
    )
    # Рамка и свечение оба «косметика», поэтому по типу надевание одного
    # молча снимало другое. Слот разводит их.
    slot = models.CharField("Слот", max_length=16, choices=ShopItemSlot.choices, blank=True)
    price_coins = models.PositiveIntegerField("Цена (монеты)")
    is_active = models.BooleanField("Активен", default=True)
    available_from = models.DateTimeField("Доступен с", null=True, blank=True)
    available_to = models.DateTimeField("Доступен до", null=True, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        indexes = [
            models.Index(fields=["is_active", "item_type"]),
            models.Index(fields=["available_from", "available_to"]),
        ]

    def __str__(self) -> str:
        return f"{self.code}: {self.title}"


class Purchase(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Пользователь",
        on_delete=models.CASCADE,
        related_name="purchases",
    )
    item = models.ForeignKey(
        ShopItem, verbose_name="Товар", on_delete=models.PROTECT, related_name="purchases"
    )
    # Баланс монет десятичный (п. 2.4 Положения), поэтому и списание тоже:
    # иначе покупка на 50 монет при балансе 50,40 оставляла бы 0,40 в воздухе.
    coins_spent = models.DecimalField("Потрачено монет", max_digits=10, decimal_places=2)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    applied_at = models.DateTimeField(
        "Применена",
        null=True,
        blank=True,
        help_text=(
            "Когда покупку сделали активной. Одновременно активна одна покупка "
            "на слот товара: рамка аватара, свечение значка, баннер профиля."
        ),
    )
    consumed_at = models.DateTimeField(
        "Использована",
        null=True,
        blank=True,
        help_text="Для буста: когда он сработал на награде за квест.",
    )
    meta = models.JSONField("Метаданные", default=dict, blank=True)

    class Meta:
        verbose_name = "Покупка"
        verbose_name_plural = "Покупки"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "applied_at"]),
        ]

    def __str__(self) -> str:
        state = " (применена)" if self.applied_at else ""
        return f"{self.user_id}:{self.item_id} (-{self.coins_spent}){state}"

    @property
    def is_applied(self) -> bool:
        return self.applied_at is not None
