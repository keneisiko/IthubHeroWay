from django.contrib.auth import get_user_model

from apps.progress.models import Characteristic, CharacteristicHistory
from apps.progress.services.lxp_characteristics import update_lxp_pillars_from_snapshot

DEFAULT_PILLARS = ("discipline", "leadership", "teamwork", "initiative", "growth")


def update_all_characteristics(formula_weights: dict | None = None) -> int:
    weights = formula_weights or {
        "discipline": 1.0,
        "leadership": 1.0,
        "teamwork": 1.0,
        "initiative": 1.0,
        "growth": 1.0,
    }
    updated = 0
    for user in get_user_model().objects.all().only("id", "rating_current"):
        for pillar in DEFAULT_PILLARS:
            metric_value = float(user.rating_current) * float(weights.get(pillar, 1.0)) / 100.0
            char_obj, _ = Characteristic.objects.get_or_create(user=user, pillar=pillar)
            char_obj.current = metric_value
            char_obj.peak = max(char_obj.peak, metric_value)
            char_obj.save(update_fields=["current", "peak", "last_updated"])
            CharacteristicHistory.objects.create(characteristic=char_obj, value=metric_value, formula_version="v1")
            updated += 1

    updated += update_lxp_pillars_from_snapshot()
    return updated
