from django.db import migrations

SLOTS = {
    "cosmetic-avatar-frame": "avatar_frame",
    "cosmetic-badge-glow": "badge_glow",
}


def fill_slots(apps, schema_editor):
    ShopItem = apps.get_model("shop", "ShopItem")
    for code, slot in SLOTS.items():
        ShopItem.objects.filter(code=code).update(slot=slot)


def clear_slots(apps, schema_editor):
    ShopItem = apps.get_model("shop", "ShopItem")
    ShopItem.objects.filter(code__in=SLOTS).update(slot="")


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0005_shop_item_slot_and_boost_consumed"),
    ]

    operations = [migrations.RunPython(fill_slots, clear_slots)]
