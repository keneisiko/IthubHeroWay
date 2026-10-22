"""Позывной студента по умолчанию.

Импорт ставил позывным логин вида «dudarkaevann25-a3b18c2c» или
«lxp_4e9bd5ea-fe4»: 16–23 символа без пробелов. Такие строки не
переносятся и распирали карточки рейтинга, отрядов и шапки. Теперь
позывной по умолчанию — «Имя Ф.», а при совпадении к нему добавляется номер.
"""

from __future__ import annotations

import re

from apps.accounts.models import User

MAX_LENGTH = 50
_LXP_CALLSIGN = re.compile(r"lxp_[0-9a-z_-]+")


def _base(first_name: str, last_name: str, fallback: str) -> str:
    first = (first_name or "").strip().split(" ")[0]
    last = (last_name or "").strip()
    if first and last:
        return f"{first} {last[0].upper()}."
    return first or last or fallback


def default_callsign(first_name: str, last_name: str, fallback: str, exclude_pk: int | None = None) -> str:
    """Свободный позывной «Имя Ф.»; занят — «Имя Ф. 2», «Имя Ф. 3»…"""
    base = _base(first_name, last_name, fallback)[:MAX_LENGTH]
    taken = User.objects.filter(callsign__startswith=base)
    if exclude_pk is not None:
        taken = taken.exclude(pk=exclude_pk)
    used = set(taken.values_list("callsign", flat=True))
    if base not in used:
        return base
    number = 2
    while True:
        candidate = f"{base[: MAX_LENGTH - len(str(number)) - 1]} {number}"
        if candidate not in used:
            return candidate
        number += 1


def is_auto_callsign(user: User) -> bool:
    """Позывной выставил импорт, а не сам студент.

    Свой позывной студента никогда не меняем — только служебные: пустой,
    совпадающий с началом логина и «lxp_…» пилотного импорта.
    """
    callsign = (user.callsign or "").strip()
    if not callsign:
        return True
    return user.username.startswith(callsign[:20]) or bool(_LXP_CALLSIGN.fullmatch(callsign))
