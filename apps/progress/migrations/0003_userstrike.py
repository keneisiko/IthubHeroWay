import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("progress", "0002_characteristics"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserStrike",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("attendance_strike", models.PositiveIntegerField(default=0, verbose_name="Дней без пропусков")),
                ("late_strike", models.PositiveIntegerField(default=0, verbose_name="Дней без опозданий")),
                (
                    "last_attendance_date",
                    models.DateField(blank=True, null=True, verbose_name="Последний день посещаемости"),
                ),
                (
                    "last_late_date",
                    models.DateField(blank=True, null=True, verbose_name="Последний день без опозданий"),
                ),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="strike",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Серия студента",
                "verbose_name_plural": "Серии студентов",
            },
        ),
    ]
