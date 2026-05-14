from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0003_lxpsnapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="HikEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.CharField(db_index=True, max_length=128, unique=True)),
                ("student_code", models.CharField(blank=True, max_length=100)),
                ("event_time", models.DateTimeField()),
                ("event_type", models.CharField(blank=True, max_length=50)),
                ("door_name", models.CharField(blank=True, max_length=200)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("processed", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-event_time"],
            },
        ),
        migrations.AddIndex(
            model_name="hikevent",
            index=models.Index(fields=["student_code", "event_time"], name="hikevent_student_time_idx"),
        ),
        migrations.AddIndex(
            model_name="hikevent",
            index=models.Index(fields=["processed", "event_time"], name="hikevent_proc_time_idx"),
        ),
    ]
