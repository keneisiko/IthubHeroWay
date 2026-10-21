from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_alter_user_coins_balance_alter_user_rating_current_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="login_blocked",
            field=models.BooleanField(
                default=False,
                help_text="Студент не сможет войти и активировать аккаунт ни на сайте, ни в боте.",
                verbose_name="Вход закрыт сотрудником",
            ),
        ),
    ]
