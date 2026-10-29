from django.conf import settings
from django.db import models


class News(models.Model):
    """Новость платформы: блок на главной и, по желанию, рассылка в бот."""

    title = models.CharField("Заголовок", max_length=120)
    body = models.TextField("Текст", max_length=1500)
    link = models.CharField(
        "Ссылка на раздел сайта",
        max_length=120,
        blank=True,
        help_text="Например /rules или /shop. Пусто — без кнопки.",
    )
    is_published = models.BooleanField("Опубликована", default=False)
    published_at = models.DateTimeField("Опубликована в", null=True, blank=True)
    sent_to_telegram_at = models.DateTimeField("Отправлена в бот", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Автор", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Новость"
        verbose_name_plural = "Новости"
        ordering = ("-published_at", "-created_at")

    def __str__(self) -> str:
        return self.title
