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
            name="Badge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("category", models.CharField(choices=[("progress", "Progress"), ("social", "Social"), ("academic", "Academic"), ("special", "Special")], default="progress", max_length=32)),
                ("rarity", models.CharField(choices=[("common", "Common"), ("rare", "Rare"), ("epic", "Epic"), ("legendary", "Legendary")], default="common", max_length=16)),
                ("condition", models.JSONField(blank=True, default=dict)),
                ("reward_coins", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [models.Index(fields=["is_active", "category"], name="apps_badges_is_acti_d5f8d7_idx")],
            },
        ),
        migrations.CreateModel(
            name="UserBadge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("acquired_at", models.DateTimeField(auto_now_add=True)),
                ("is_pinned", models.BooleanField(default=False)),
                ("source", models.CharField(blank=True, max_length=64)),
                ("badge", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="awarded_users", to="badges.badge")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="badges", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["user", "-acquired_at"], name="apps_badges_user_id_a742a3_idx"), models.Index(fields=["user", "is_pinned"], name="apps_badges_user_id_7d058e_idx")],
                "unique_together": {("user", "badge")},
            },
        ),
    ]

