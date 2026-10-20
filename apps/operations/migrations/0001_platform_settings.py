import django.core.validators
from django.db import migrations, models


def seed_current_values(apps, schema_editor):
    """Строка с теми значениями, что действуют сейчас.

    Значения берутся из прежних мест — RATING_LIMITS, polozhenie.py и
    переменных окружения на сервере, — поэтому после миграции поведение
    платформы не меняется ни на единицу, пока кто-то не поправит настройку.
    """
    from apps.operations.services.platform_settings import default_values

    PlatformSettings = apps.get_model("operations", "PlatformSettings")
    PlatformSettings.objects.update_or_create(pk=1, defaults=default_values())


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PlatformSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("max_daily_coins", models.PositiveIntegerField(help_text="Сколько монет студент может получить за день из квестов и нашивок. Начисления по Положению (разделы 3–7) через предел не проходят.", validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10000)], verbose_name="Дневной предел монет")),
                ("max_daily_self_reports", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)], verbose_name="Самоотчётов в день")),
                ("squad_weekly_bonus_percent", models.PositiveIntegerField(help_text="Какая доля отряда должна закрыть недельный квест, чтобы бонус получили все.", validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)], verbose_name="Командный бонус: доля отряда, %")),
                ("squad_weekly_bonus_coins", models.PositiveIntegerField(validators=[django.core.validators.MaxValueValidator(1000)], verbose_name="Командный бонус: монет каждому")),
                ("respect_weekly_limit", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(50)], verbose_name="Респектов в неделю от одного студента")),
                ("duel_bet", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(1000)], verbose_name="Ставка в дуэли, монет")),
                ("duel_duration_days", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(60)], verbose_name="Длительность дуэли, дней")),
                ("duel_invite_ttl_days", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(30)], verbose_name="Вызов на дуэль ждёт ответа, дней")),
                ("duel_max_rating_diff", models.PositiveIntegerField(help_text="Нельзя вызвать соперника, чей рейтинг отличается сильнее.", validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10000)], verbose_name="Макс. разница рейтинга для дуэли")),
                ("hik_late_grace_minutes", models.PositiveIntegerField(help_text="Проход через турникет позже начала пары на это число минут ещё не опоздание.", validators=[django.core.validators.MaxValueValidator(60)], verbose_name="Допуск опоздания, минут")),
                ("ct_scope", models.CharField(choices=[("deferred", "Отложено: компонент КТ не начисляется, копится"), ("decided", "Только сданные и не сданные темы"), ("decided_with_pending", "Плюс темы на проверке")], help_text="Пока колледж не выбрал правило, компонент КТ не начисляется и копится. После выбора недоплаченное начисляется командой accrue_week --since.", max_length=32, verbose_name="Правило учёта КТ")),
                ("ct_min_actual", models.PositiveIntegerField(help_text="Если актуальных тем меньше, процент не считается — слишком мало данных.", validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)], verbose_name="Минимум актуальных КТ для расчёта")),
                ("require_telegram_link_for_scoring", models.BooleanField(help_text="Выключено по Положению (п. 2.1–2.2): начисления идут всем студентам. Включать только для закрытых прогонов.", verbose_name="Начислять только привязавшим Telegram")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Изменено")),
            ],
            options={
                "verbose_name": "Настройки платформы",
                "verbose_name_plural": "Настройки платформы",
            },
        ),
        migrations.RunPython(seed_current_values, migrations.RunPython.noop),
    ]
