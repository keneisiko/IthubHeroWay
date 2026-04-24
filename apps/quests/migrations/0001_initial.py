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
            name="Quest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("quest_type", models.CharField(choices=[("daily", "Daily"), ("weekly", "Weekly"), ("event", "Event"), ("long", "Long")], default="daily", max_length=16)),
                ("reward_coins", models.PositiveIntegerField(default=0)),
                ("reward_rating_delta", models.IntegerField(default=0)),
                ("conditions", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("start_at", models.DateTimeField(blank=True, null=True)),
                ("end_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [models.Index(fields=["is_active", "quest_type"], name="apps_quests_is_acti_3f1b8d_idx"), models.Index(fields=["start_at", "end_at"], name="apps_quests_start_a_248911_idx")],
            },
        ),
        migrations.CreateModel(
            name="UserQuestProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("progress_value", models.FloatField(default=0)),
                ("is_completed", models.BooleanField(default=False)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("proof_payload", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("quest", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_progress", to="quests.quest")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quest_progress", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["user", "is_completed"], name="apps_quests_user_id_d7f95d_idx"), models.Index(fields=["updated_at"], name="apps_quests_updated_783116_idx")],
                "unique_together": {("user", "quest")},
            },
        ),
    ]

