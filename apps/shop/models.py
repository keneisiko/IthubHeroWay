from django.conf import settings
from django.db import models


class ShopItemType(models.TextChoices):
    COSMETIC = "cosmetic", "Косметика"
    BOOST = "boost", "Усиление"
    SERVICE = "service", "Услуга"
    OTHER = "other", "Прочее"


class ShopItem(models.Model):
    code = models.CharField("Код", max_length=64, unique=True)
    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    item_type = models.CharField(
        "Тип товара", max_length=16, choices=ShopItemType.choices, default=ShopItemType.OTHER
    )
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
    coins_spent = models.PositiveIntegerField("Потрачено монет")
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    meta = models.JSONField("Метаданные", default=dict, blank=True)

    class Meta:
        verbose_name = "Покупка"
        verbose_name_plural = "Покупки"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.item_id} (-{self.coins_spent})"
