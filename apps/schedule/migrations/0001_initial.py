import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0005_user_hik_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="Schedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "day_of_week",
                    models.IntegerField(
                        choices=[
                            (0, "Понедельник"),
                            (1, "Вторник"),
                            (2, "Среда"),
                            (3, "Четверг"),
                            (4, "Пятница"),
                            (5, "Суббота"),
                            (6, "Воскресенье"),
                        ],
                        verbose_name="День недели",
                    ),
                ),
                ("start_time", models.TimeField(verbose_name="Начало")),
                ("end_time", models.TimeField(verbose_name="Окончание")),
                ("discipline", models.CharField(blank=True, max_length=200, verbose_name="Дисциплина")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активно")),
                (
                    "squad",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="schedule_slots",
                        to="accounts.squad",
                        verbose_name="Отряд",
                    ),
                ),
            ],
            options={
                "verbose_name": "Слот расписания",
                "verbose_name_plural": "Расписание",
                "ordering": ["day_of_week", "start_time"],
            },
        ),
        migrations.AddConstraint(
            model_name="schedule",
            constraint=models.UniqueConstraint(
                fields=("squad", "day_of_week", "start_time"),
                name="uniq_schedule_squad_day_start",
            ),
        ),
    ]
