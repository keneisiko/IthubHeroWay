from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("progress", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Characteristic",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pillar", models.CharField(db_index=True, max_length=32)),
                ("current", models.FloatField(default=0)),
                ("peak", models.FloatField(default=0)),
                ("last_updated", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="characteristics",
                        to="accounts.user",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CharacteristicHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.FloatField()),
                ("formula_version", models.CharField(default="v1", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "characteristic",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="history_entries",
                        to="progress.characteristic",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="characteristic",
            constraint=models.UniqueConstraint(fields=("user", "pillar"), name="uniq_characteristic_per_user_pillar"),
        ),
    ]

