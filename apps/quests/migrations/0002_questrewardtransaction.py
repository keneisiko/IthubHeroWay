import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("quests", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuestRewardTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("coins_delta", models.IntegerField(default=0)),
                ("rating_delta", models.IntegerField(default=0)),
                ("granted_at", models.DateTimeField(auto_now_add=True)),
                ("progress", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reward_transactions", to="quests.userquestprogress")),
                ("quest", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reward_transactions", to="quests.quest")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quest_rewards", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["user", "-granted_at"], name="apps_quests_user_id_06454f_idx")],
                "unique_together": {("user", "quest")},
            },
        ),
    ]

