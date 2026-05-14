from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_user_lxp_user_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="hik_card_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Код карты / personCode для HikCentral (привязка проходов к пользователю)",
                max_length=100,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="hik_person_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Идентификатор лица в HikCentral при наличии",
                max_length=100,
                null=True,
            ),
        ),
    ]
