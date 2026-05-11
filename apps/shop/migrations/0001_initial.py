import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ShopItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("item_type", models.CharField(choices=[("cosmetic", "Cosmetic"), ("boost", "Boost"), ("service", "Service"), ("other", "Other")], default="other", max_length=16)),
                ("price_coins", models.PositiveIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("available_from", models.DateTimeField(blank=True, null=True)),
                ("available_to", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [models.Index(fields=["is_active", "item_type"], name="apps_shop_s_is_acti_f843af_idx"), models.Index(fields=["available_from", "available_to"], name="apps_shop_s_availab_98fe84_idx")],
            },
        ),
        migrations.CreateModel(
            name="Purchase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("coins_spent", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchases", to="shop.shopitem")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="purchases", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["user", "-created_at"], name="apps_shop_p_user_id_8da942_idx")],
            },
        ),
    ]

