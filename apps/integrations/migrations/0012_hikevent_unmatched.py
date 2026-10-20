from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0011_hikevent_last_error_hikevent_process_attempts"),
    ]

    operations = [
        migrations.AddField(
            model_name="hikevent",
            name="unmatched",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Владелец прохода неизвестен. Снимается автоматически, когда студента свяжут с Hik.",
                verbose_name="Студент не найден",
            ),
        ),
    ]
