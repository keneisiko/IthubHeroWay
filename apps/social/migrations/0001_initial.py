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
            name="Duel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("rejected", "Rejected")], default="pending", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("challenger", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="duels_started", to=settings.AUTH_USER_MODEL)),
                ("opponent", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="duels_received", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["status", "-created_at"], name="apps_social_status_1c254c_idx")],
            },
        ),
        migrations.CreateModel(
            name="Respect",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("from_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="respects_given", to=settings.AUTH_USER_MODEL)),
                ("to_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="respects_received", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["to_user", "-created_at"], name="apps_social_to_user_a9d6e5_idx")],
            },
        ),
        migrations.CreateModel(
            name="Mentorship",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("mentee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mentors", to=settings.AUTH_USER_MODEL)),
                ("mentor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mentees", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["mentor", "mentee"], name="apps_social_mentor__a54476_idx")],
                "unique_together": {("mentor", "mentee")},
            },
        ),
    ]

