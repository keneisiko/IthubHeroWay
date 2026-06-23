from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quests", "0005_alter_quest_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuestTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True, verbose_name="Код")),
                ("title", models.CharField(max_length=255, verbose_name="Название")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                (
                    "quest_type",
                    models.CharField(
                        choices=[
                            ("daily", "Ежедневный"),
                            ("weekly", "Еженедельный"),
                            ("event", "Событийный"),
                            ("long", "Долгий"),
                            ("self_report", "Самоотчёт"),
                            ("mixed", "Смешанный"),
                        ],
                        default="daily",
                        max_length=16,
                        verbose_name="Тип квеста",
                    ),
                ),
                (
                    "verifier",
                    models.CharField(
                        choices=[
                            ("manual", "Вручную"),
                            ("hik_on_time", "Hik: вовремя"),
                            ("hik_no_late", "Hik: без опозданий"),
                            ("lxp_attendance", "LXP: посещаемость"),
                            ("lxp_ct_closed", "LXP: закрытые КТ"),
                            ("yougile_tasks", "YouGile: задачи"),
                            ("late_streak", "Серия без опозданий"),
                        ],
                        default="manual",
                        max_length=32,
                        verbose_name="Проверка",
                    ),
                ),
                ("verifier_params", models.JSONField(blank=True, default=dict, verbose_name="Параметры проверки")),
                ("reward_coins", models.PositiveIntegerField(default=0, verbose_name="Награда (монеты)")),
                ("reward_rating_delta", models.IntegerField(default=0, verbose_name="Награда (рейтинг)")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
            ],
            options={
                "verbose_name": "Шаблон квеста",
                "verbose_name_plural": "Шаблоны квестов",
                "ordering": ["quest_type", "code"],
            },
        ),
    ]
