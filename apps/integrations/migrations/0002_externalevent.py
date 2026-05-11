from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(db_index=True, max_length=32)),
                ("external_event_id", models.CharField(max_length=128)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("processed_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [models.Index(fields=["source", "-processed_at"], name="integrations_source_536f0b_idx")],
            },
        ),
        migrations.AddConstraint(
            model_name="externalevent",
            constraint=models.UniqueConstraint(
                fields=("source", "external_event_id"), name="uniq_external_event_per_source"
            ),
        ),
    ]

