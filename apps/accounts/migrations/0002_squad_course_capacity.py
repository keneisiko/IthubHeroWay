from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="squad",
            name="course",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="squad",
            name="capacity",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]

