"""Направление (трек) студента по названию его группы.

Справочник направлений был пуст, и в профиле у всех стояло «Трек: —», хотя
направление уже зашито в название группы: «3ИТР2.9.24» — курс, код
специальности, номер группы, год набора. В колледже три направления;
ИБ, ИИ и все ИТ-группы — программисты.
"""

from __future__ import annotations

import re

from apps.accounts.models import Track, User

# код специальности из названия группы → (код направления, название)
TRACK_BY_GROUP_CODE: dict[str, tuple[str, str]] = {
    "Д": ("design", "Дизайн"),
    "М": ("marketing", "Маркетинг"),
    "ИТ": ("programming", "Программирование"),
    "ИТП": ("programming", "Программирование"),
    "ИТР": ("programming", "Программирование"),
    "ИИ": ("programming", "Программирование"),
    "ИБ": ("programming", "Программирование"),
}

_GROUP_CODE = re.compile(r"\s*[1-4]([А-ЯЁ]+)")


def track_for_group(name: str) -> Track | None:
    """Направление для группы или None, если код специальности незнакомый.

    Незнакомый код не угадываем: пустой трек честнее неверного.
    """
    match = _GROUP_CODE.match((name or "").upper())
    if not match or match.group(1) not in TRACK_BY_GROUP_CODE:
        return None
    code, title = TRACK_BY_GROUP_CODE[match.group(1)]
    track, _ = Track.objects.get_or_create(code=code, defaults={"name": title})
    return track


def assign_track_if_empty(user: User, group_name: str) -> bool:
    """Проставить трек по группе, если он ещё не задан.

    Заданный трек не трогаем: его мог поправить сотрудник в админке.
    """
    if user.track_id:
        return False
    track = track_for_group(group_name)
    if track is None:
        return False
    user.track = track
    user.save(update_fields=["track"])
    return True
