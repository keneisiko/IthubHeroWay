from django.db import migrations
from django.utils import timezone


def consume_legacy(apps, schema_editor):
    """Покупки снятых бустов (тип boost без слота) ничего не делали: гасим их,
    чтобы они не стали рабочим ×2 и не блокировали покупку нового буста."""
    Purchase = apps.get_model("shop", "Purchase")
    Purchase.objects.filter(
        item__item_type="boost", item__slot="", consumed_at__isnull=True
    ).update(consumed_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0006_fill_item_slots"),
    ]

    operations = [migrations.RunPython(consume_legacy, migrations.RunPython.noop)]
