"""Удалить синтетические привязки Telegram.

Эндпоинты создания и вступления в отряд молча создавали `TelegramAccountLink`
с выдуманным `telegram_user_id = 5_100_000_000 + user_id`. Такая привязка
обходила гейт «участвует в рейтинге только активированный в боте» и рисковала
конфликтовать с реальным Telegram ID: у живых аккаунтов они давно перешагнули
5 млрд, а поле уникально.

Удаляем только записи, точно совпадающие с формулой, — настоящие привязки
под неё попасть не могут, кроме астрономически маловероятного совпадения,
которое проверяется дополнительно по chat_id и пустому имени пользователя.
"""

from django.db import migrations

SYNTHETIC_TELEGRAM_BASE = 5_100_000_000


def remove_synthetic_links(apps, schema_editor):
    TelegramAccountLink = apps.get_model("integrations", "TelegramAccountLink")

    removed = 0
    for link in TelegramAccountLink.objects.all().iterator(chunk_size=500):
        expected = SYNTHETIC_TELEGRAM_BASE + int(link.user_id)
        # Синтетическая запись: id и chat_id совпадают с формулой,
        # а имя пользователя пустое (бот его всегда заполняет).
        if (
            link.telegram_user_id == expected
            and link.telegram_chat_id == expected
            and not (link.telegram_username or "").strip()
        ):
            link.delete()
            removed += 1

    if removed:
        print(f"  удалено синтетических привязок Telegram: {removed}")


def noop(apps, schema_editor):
    """Обратная миграция не восстанавливает фейковые записи намеренно."""


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0007_hikimportrun"),
    ]

    operations = [
        migrations.RunPython(remove_synthetic_links, noop),
    ]
