"""Импорт учебной группы LXP в отряд платформы.

Логика жила внутри management-команды для одной группы. Когда понадобилось
завести весь колледж, оказалось, что повторить её для каждой группы можно
только копированием, — поэтому она здесь, а команды только решают, какие
группы брать и как их назвать.

Связь `Squad.lxp_group_id` обязательна: по ней ночные задачи знают, откуда
брать расписание и отметки посещения. Отряд без неё — отряд без
посещаемости, то есть без единственного компонента, который сейчас
начисляется по Положению.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from django.db import transaction

from apps.accounts.models import Role, Squad, User
from apps.accounts.tracks import assign_track_if_empty
from apps.integrations.services.lxp_groups import group_students

# Транслитерация для кода отряда: код уходит в адреса и в админку, поэтому
# он латиницей, а название остаётся русским.
TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


@dataclass(frozen=True)
class GroupImportResult:
    squad_code: str
    squad_name: str
    course: int
    students: int
    created: int
    matched: int
    squad_created: bool


def transliterate(raw: str) -> str:
    return "".join(TRANSLIT.get(ch, ch) for ch in (raw or "").lower())


def slug(raw: str, fallback: str) -> str:
    value = re.sub(r"[^a-z0-9._-]+", "-", transliterate(raw).strip()).strip("._-")
    return value[:50] or fallback


def course_from_name(name: str) -> int:
    """Курс по названию группы: «3ИТР2.9.24» — третий курс.

    Номер курса стоит первым символом во всех названиях колледжа. Если его
    там нет, курс не угадывается: лучше пропустить группу и спросить, чем
    поставить наугад и разойтись с реальностью в отчётах по курсам.
    """
    match = re.match(r"\s*([1-4])", name or "")
    return int(match.group(1)) if match else 0


def squad_code_for(group: dict) -> str:
    return slug(group.get("name") or "", fallback=f"lxp-{group.get('id', '')}"[:50])


def _create_user(lxp_user_id: str, email: str, first_name: str, last_name: str) -> User:
    base = slug(email.split("@", 1)[0] if email else lxp_user_id, fallback="student")
    username = (f"{base}-{lxp_user_id[:8]}" if lxp_user_id else base)[:150]
    callsign = username[:50]
    suffix = 1
    while User.objects.filter(callsign=callsign).exists():
        suffix += 1
        callsign = f"{username[:45]}-{suffix}"[:50]
    user = User(
        username=username,
        email=email or "",
        first_name=first_name,
        last_name=last_name,
        callsign=callsign,
        role=Role.AGENT,
        lxp_user_id=lxp_user_id or None,
        # Карточка создаётся закрытой: пароль от LXP знает и сам студент,
        # подтверждением личности служит привязка Telegram.
        is_active=False,
    )
    # Локального пароля у студента быть не должно вовсе: вход идёт через
    # проверку в LXP. Без этого вызова поле остаётся пустой строкой, которую
    # Django считает годным паролем, и появляется второй, более слабый вход.
    user.set_unusable_password()
    user.save()
    return user


@transaction.atomic
def import_group(
    *, group_id: str, squad_code: str, squad_name: str, course: int, students: list | None = None
) -> GroupImportResult:
    """Завести отряд по группе LXP и привязать к нему студентов."""
    rows = students if students is not None else group_students(group_id)

    # Сначала по группе LXP, и только потом по коду. Отряд пилота был заведён
    # руками с кодом `itr2-24`, а транслитерация даёт `3itr2.9.24`: поиск
    # по одному коду создал бы второй отряд на ту же группу, и ночные задачи
    # грузили бы ей расписание и отметки дважды.
    squad = None
    squad_created = False
    if group_id:
        squad = Squad.objects.filter(lxp_group_id=group_id).first()
    if squad is None:
        squad = Squad.objects.filter(code=squad_code).first()
    if squad is None:
        squad = Squad.objects.create(
            code=squad_code, name=squad_name, course=course, lxp_group_id=group_id
        )
        squad_created = True

    changed = []
    if squad.name != squad_name:
        squad.name = squad_name
        changed.append("name")
    if squad.course != course:
        squad.course = course
        changed.append("course")
    if squad.lxp_group_id != group_id:
        squad.lxp_group_id = group_id
        changed.append("lxp_group_id")
    if changed:
        squad.save(update_fields=changed)

    created = matched = 0
    for item in rows:
        user_data = item.get("user") or {}
        lxp_user_id = str(user_data.get("id") or item.get("id") or "")
        email = (user_data.get("email") or "").strip().lower()
        first_name = (user_data.get("firstName") or "").strip()
        last_name = (user_data.get("lastName") or "").strip()

        # Импорт всего колледжа мог уже завести карточку: ищем по id LXP,
        # затем по почте, и только потом создаём новую.
        user = None
        if lxp_user_id:
            user = User.objects.filter(lxp_user_id=lxp_user_id).first()
        if user is None and email:
            user = User.objects.filter(email__iexact=email).first()

        if user is None:
            user = _create_user(lxp_user_id, email, first_name, last_name)
            created += 1
        else:
            matched += 1

        fields = []
        if user.squad_id != squad.id:
            user.squad = squad
            fields.append("squad")
        if lxp_user_id and user.lxp_user_id != lxp_user_id:
            user.lxp_user_id = lxp_user_id
            fields.append("lxp_user_id")
        if first_name and not user.first_name:
            user.first_name = first_name
            fields.append("first_name")
        if last_name and not user.last_name:
            user.last_name = last_name
            fields.append("last_name")
        if fields:
            user.save(update_fields=fields)
        assign_track_if_empty(user, squad.name)

    return GroupImportResult(
        squad_code=squad.code,
        squad_name=squad.name,
        course=squad.course,
        students=len(rows),
        created=created,
        matched=matched,
        squad_created=squad_created,
    )
