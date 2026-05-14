from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_unclosed_ct_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="lxp_user_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Идентификатор пользователя в LXP (GraphQL user.id), для связи со снимком",
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]
