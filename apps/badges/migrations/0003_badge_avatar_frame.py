from django.db import migrations, models


def mark_developer_badge(apps, schema_editor):
    # Нашивку «Разработчик» заводили в админке вручную, код у неё свой
    # на каждом стенде — узнаём её по названию.
    Badge = apps.get_model("badges", "Badge")
    Badge.objects.filter(title__iexact="Разработчик").update(avatar_frame="developer")


class Migration(migrations.Migration):
    dependencies = [
        ("badges", "0002_alter_badge_options_alter_userbadge_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="badge",
            name="avatar_frame",
            field=models.CharField(
                blank=True,
                choices=[("", "Без рамки"), ("developer", "Рамка разработчика")],
                default="",
                help_text="Владелец нашивки получает особую рамку аватара на всём сайте.",
                max_length=16,
                verbose_name="Рамка аватара",
            ),
        ),
        migrations.RunPython(mark_developer_badge, migrations.RunPython.noop),
    ]
