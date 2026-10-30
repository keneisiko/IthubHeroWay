from django.db import migrations, models


def add_halloween_badge(apps, schema_editor):
    # Сезонная нашивка выдаётся вручную в админке: «Самый страшный» —
    # за самый жуткий образ на Хэллоуин. Даёт рамку-склеп и тему профиля.
    Badge = apps.get_model("badges", "Badge")
    Badge.objects.update_or_create(
        code="halloween-scariest",
        defaults={
            "title": "Самый страшный",
            "description": "За самый жуткий образ на Хэллоуин 2026. Выдаёт куратор.",
            "category": "special",
            "rarity": "legendary",
            "condition": {"manual": True},
            "avatar_frame": "halloween",
            "is_active": True,
        },
    )


def remove_halloween_badge(apps, schema_editor):
    Badge = apps.get_model("badges", "Badge")
    Badge.objects.filter(code="halloween-scariest", awarded_users__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("badges", "0003_badge_avatar_frame"),
    ]

    operations = [
        migrations.AlterField(
            model_name="badge",
            name="avatar_frame",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Без рамки"),
                    ("developer", "Рамка разработчика"),
                    ("halloween", "Хэллоуин: склеп «Самый страшный»"),
                ],
                default="",
                help_text="Владелец нашивки получает особую рамку аватара на всём сайте и тему профиля, пока нашивка закреплена.",
                max_length=16,
                verbose_name="Рамка аватара",
            ),
        ),
        migrations.RunPython(add_halloween_badge, remove_halloween_badge),
    ]
