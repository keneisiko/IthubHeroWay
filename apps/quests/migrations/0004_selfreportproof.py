from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("quests", "0003_seasonalevent_squadleaderboardsnapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="SelfReportProof",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("comment", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], db_index=True, default="pending", max_length=16)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("quest", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="self_report_proofs", to="quests.quest")),
                (
                    "quest_progress",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="self_report_proof",
                        to="quests.userquestprogress",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="self_report_reviews",
                        to="accounts.user",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="self_report_proofs",
                        to="accounts.user",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="selfreportproof",
            index=models.Index(fields=["status", "-created_at"], name="quests_self_status_9c1d3a_idx"),
        ),
        migrations.AddIndex(
            model_name="selfreportproof",
            index=models.Index(fields=["user", "-created_at"], name="quests_self_user_id_41d4c3_idx"),
        ),
    ]

