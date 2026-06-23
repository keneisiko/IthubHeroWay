from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0005_alter_externalevent_options_alter_hikevent_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="HikSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(unique=True, verbose_name="Дата")),
                ("data", models.JSONField(verbose_name="Данные")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
            ],
            options={
                "verbose_name": "Снимок Hik",
                "verbose_name_plural": "Снимки Hik",
                "ordering": ["-date"],
            },
        ),
    ]
