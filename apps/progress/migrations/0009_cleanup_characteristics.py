"""Убрать характеристики, которые нигде не показываются и посчитаны неверно.

- `leadership` и `growth` пересчёт заводил всем, но в пятиугольнике их нет;
- характеристики сотрудников — пятиугольник показывается только студентам;
- история формулы `v1` («рейтинг ÷ 100» для Фокуса, Связи и Отдачи): иначе
  график истории по оси показывал бы старые бессмысленные точки.
"""

from django.db import migrations

UI_PILLARS = ("rhythm", "discipline", "power", "teamwork", "initiative")


def cleanup(apps, schema_editor):
    Characteristic = apps.get_model("progress", "Characteristic")
    History = apps.get_model("progress", "CharacteristicHistory")
    Characteristic.objects.exclude(pillar__in=UI_PILLARS).delete()
    Characteristic.objects.exclude(user__role="agent").delete()
    History.objects.filter(formula_version="v1").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("progress", "0008_ratinglog_coins_delta_ratinglog_confirmed_by_and_more"),
        ("accounts", "0010_backfill_login_blocked"),
    ]

    operations = [migrations.RunPython(cleanup, migrations.RunPython.noop)]
