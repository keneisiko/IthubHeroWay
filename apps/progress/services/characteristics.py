"""Еженедельный пересчёт пяти опор пятиугольника.

«Мощность» и «Ритм» — из снимка LXP (lxp_characteristics), «Фокус», «Связь»
и «Отдача» — из активности на платформе (activity_pillars). Считаются только
студенты: сотрудникам пятиугольник не показывается, а раньше на них уходили
строки и история каждую неделю.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import Role
from apps.progress.services.activity_pillars import activity_pillars
from apps.progress.services.lxp_characteristics import save_pillar, update_lxp_pillars_from_snapshot

FORMULA_VERSION = "activity_v1"


def update_all_characteristics() -> int:
    today = timezone.localdate()
    updated = 0
    students = get_user_model().objects.filter(role=Role.AGENT).only("id")
    for user in students.iterator(chunk_size=200):
        for pillar, value in activity_pillars(user.pk, today).items():
            if value is None:
                continue
            save_pillar(user, pillar, value, FORMULA_VERSION)
            updated += 1

    updated += update_lxp_pillars_from_snapshot()
    return updated
