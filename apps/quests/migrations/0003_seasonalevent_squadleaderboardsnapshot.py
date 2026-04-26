from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_user_unclosed_ct_count"),
        ("quests", "0002_questrewardtransaction"),
    ]

    operations = [
        migrations.CreateModel(
            name="SeasonalEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("progress_percent", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=False)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="SquadLeaderboardSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("avg_rating", models.FloatField(default=0)),
                ("agents_count", models.PositiveIntegerField(default=0)),
                ("captured_at", models.DateTimeField(auto_now_add=True)),
                (
                    "squad",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="leaderboard_snapshots",
                        to="accounts.squad",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="seasonalevent",
            index=models.Index(fields=["is_active"], name="quests_seas_is_acti_425539_idx"),
        ),
        migrations.AddIndex(
            model_name="seasonalevent",
            index=models.Index(fields=["started_at", "ended_at"], name="quests_seas_started_89f536_idx"),
        ),
        migrations.AddIndex(
            model_name="squadleaderboardsnapshot",
            index=models.Index(fields=["-captured_at"], name="quests_squa_captured_f5262e_idx"),
        ),
        migrations.AddIndex(
            model_name="squadleaderboardsnapshot",
            index=models.Index(fields=["squad", "-captured_at"], name="quests_squa_squad_i_a33e78_idx"),
        ),
    ]

