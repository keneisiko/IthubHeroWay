from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_squad_course_capacity"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="unclosed_ct_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]

