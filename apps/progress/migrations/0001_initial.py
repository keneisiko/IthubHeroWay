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
            name="RatingLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value_before", models.IntegerField()),
                ("value_after", models.IntegerField()),
                ("delta", models.IntegerField()),
                ("source", models.CharField(choices=[("quest", "Quest"), ("badge", "Badge"), ("shop", "Shop"), ("social", "Social"), ("manual", "Manual"), ("system", "System")], default="system", max_length=16)),
                ("source_id", models.CharField(blank=True, max_length=64)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rating_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["user", "-created_at"], name="apps_progre_user_id_6c3211_idx"), models.Index(fields=["source"], name="apps_progre_source_042e13_idx")],
            },
        ),
    ]

