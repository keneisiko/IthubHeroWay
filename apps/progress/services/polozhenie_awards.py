"""Начисления по разделам 4-7 Положения и списания по разделу 9.

Разделы отличаются только тарифом и правилом «что считается одним и тем же
действием»:

* роли (4) — еженедельно, пропорционально дням действия статуса;
* мероприятия (5) — одна наивысшая подтверждённая роль на мероприятие;
* олимпиады (6) — один тариф по наивысшему результату, победа после
  засчитанного участия оплачивается разницей;
* проекты (7) — по принятому результату, одна работа не оплачивается дважды;
* списания (9) — 1 балл за пропущенную пару, максимум 4 за день, только
  рейтинг.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from apps.accounts.models import User
from apps.progress.models import (
    LessonAttendance,
    LessonAttendanceStatus,
    PolozhenieAward,
    PolozhenieAwardKind,
    RatingChangeSource,
    StudentRoleAssignment,
)
from apps.progress.services.polozhenie_ledger import grant
from apps.progress.services.polozhenie_period import (
    is_payable_week,
    period_key,
    quantize_money,
    week_end,
    week_start,
)

logger = logging.getLogger(__name__)

# п. 4.2: за неполную неделю начисление пропорционально числу учебных дней
# действия роли. Учебная неделя — пять дней, суббота и воскресенье в знаменатель
# не входят.
SCHOOL_DAYS_PER_WEEK = 5


class UnknownTariff(ValueError):
    pass


@dataclass(frozen=True)
class AwardOutcome:
    granted: bool
    rating: Decimal
    coins: Decimal
    note: str = ""


# --- Раздел 4: регулярные роли ----------------------------------------------


def _role_tariff(kind: str) -> dict:
    tariffs = getattr(settings, "POLOZHENIE_ROLES", {})
    if kind not in tariffs:
        raise UnknownTariff(f"Неизвестная роль: {kind}")
    return tariffs[kind]


def school_days_active(assignment: StudentRoleAssignment, start: date, end: date) -> int:
    """Сколько учебных дней недели роль действовала."""
    days = 0
    day = start
    while day <= end:
        if day.weekday() < SCHOOL_DAYS_PER_WEEK and assignment.is_active_on(day):
            days += 1
        day += timedelta(days=1)
    return days


def accrue_roles_for_user(user: User, day: date) -> AwardOutcome:
    """Начислить студенту за все действующие роли на неделе (п. 4.1-4.3)."""
    start, end = week_start(day), week_end(day)
    if not is_payable_week(start):
        return AwardOutcome(False, Decimal("0"), Decimal("0"), "before_season_start")

    key = period_key(start)
    total_rating = Decimal("0")
    total_coins = Decimal("0")
    paid_any = False

    assignments = StudentRoleAssignment.objects.filter(user=user, started_on__lte=end).exclude(
        ended_on__lt=start
    )
    for assignment in assignments:
        days = school_days_active(assignment, start, end)
        if days == 0:
            continue
        try:
            tariff = _role_tariff(assignment.kind)
        except UnknownTariff:
            logger.warning("Неизвестная роль %s у студента %s", assignment.kind, user.pk)
            continue

        share = Decimal(days) / Decimal(SCHOOL_DAYS_PER_WEEK)
        rating = quantize_money(Decimal(str(tariff["rating"])) * share)
        coins = quantize_money(Decimal(str(tariff["coins"])) * share)

        # Совмещаемые роли оплачиваются отдельно (п. 4.2), поэтому ключ
        # идемпотентности включает вид роли, а не только неделю.
        res = grant(
            user,
            rating=rating,
            coins=coins,
            source=RatingChangeSource.ROLE,
            source_id=f"role:{assignment.kind}:{key}",
            reason=f"{tariff['title']} за {key} ({days} из {SCHOOL_DAYS_PER_WEEK} дн.)",
            period=key,
            confirmed_by=assignment.confirmed_by,
        )
        if res.applied:
            paid_any = True
            total_rating += res.rating_delta
            total_coins += res.coins_delta

    return AwardOutcome(paid_any, total_rating, total_coins)


def run_weekly_roles(day: date | None = None) -> dict:
    """Начисления за роли всем, у кого есть подтверждённый статус."""
    from django.utils import timezone

    day = day or timezone.localdate()
    start, end = week_start(day), week_end(day)
    user_ids = (
        StudentRoleAssignment.objects.filter(started_on__lte=end)
        .exclude(ended_on__lt=start)
        .values_list("user_id", flat=True)
        .distinct()
    )
    paid = 0
    rating_total = Decimal("0")
    coins_total = Decimal("0")
    for user in User.objects.filter(pk__in=list(user_ids)).iterator(chunk_size=200):
        outcome = accrue_roles_for_user(user, day)
        if outcome.granted:
            paid += 1
            rating_total += outcome.rating
            coins_total += outcome.coins
    return {
        "period": period_key(start),
        "paid": paid,
        "rating": rating_total,
        "coins": coins_total,
    }


# --- Разделы 5-6: мероприятия и олимпиады -----------------------------------


def _rank(sequence: tuple[str, ...], value: str) -> int:
    """Старшинство роли или результата: чем больше, тем выше."""
    try:
        return sequence.index(value)
    except ValueError as exc:
        raise UnknownTariff(f"Неизвестное значение: {value}") from exc


def _award_activity(
    user: User,
    *,
    kind: str,
    activity_key: str,
    title: str,
    level: str,
    role: str,
    happened_on: date,
    tariffs: dict,
    role_order: tuple[str, ...],
    levels: tuple[str, ...],
    source: str,
    label: str,
    confirmed_by: User | None,
    note: str,
) -> AwardOutcome:
    """Общая механика разделов 5 и 6.

    Одна активность — одно начисление по наивысшей подтверждённой роли.
    Если роль выше уже засчитанной, начисляется разница; если ниже или равна,
    не начисляется ничего.
    """
    if level not in levels:
        raise UnknownTariff(f"Неизвестный уровень: {level}")
    new_rank = _rank(role_order, role)
    tariff = tariffs.get((role, level))
    if tariff is None:
        raise UnknownTariff(f"Нет тарифа для {role}/{level}")
    rating_full, coins_full = (Decimal(str(tariff[0])), Decimal(str(tariff[1])))

    with transaction.atomic():
        existing = (
            PolozhenieAward.objects.select_for_update()
            .filter(user=user, kind=kind, activity_key=activity_key)
            .first()
        )

        if existing is not None:
            old_rank = _rank(role_order, existing.role) if existing.role in role_order else -1
            if new_rank <= old_rank:
                # п. 5.2 и 6.3: применяется один тариф по наивысшему
                # подтверждённому результату, повторно ничего не начисляется.
                return AwardOutcome(False, Decimal("0"), Decimal("0"), "lower_or_equal_role")
            rating_delta = rating_full - existing.rating_granted
            coins_delta = coins_full - existing.coins_granted
            suffix = f":{role}"
        else:
            rating_delta = rating_full
            coins_delta = coins_full
            suffix = ""

        res = grant(
            user,
            rating=rating_delta,
            coins=coins_delta,
            source=source,
            source_id=f"{kind}:{activity_key}{suffix}"[:64],
            reason=f"{label}: {title or activity_key} ({role}/{level})",
            confirmed_by=confirmed_by,
        )
        if not res.applied:
            return AwardOutcome(False, Decimal("0"), Decimal("0"), res.reason)

        if existing is not None:
            existing.role = role
            existing.level = level
            existing.title = title or existing.title
            existing.rating_granted = rating_full
            existing.coins_granted = coins_full
            existing.confirmed_by = confirmed_by or existing.confirmed_by
            existing.note = note or existing.note
            existing.save(
                update_fields=[
                    "role",
                    "level",
                    "title",
                    "rating_granted",
                    "coins_granted",
                    "confirmed_by",
                    "note",
                ]
            )
        else:
            PolozhenieAward.objects.create(
                user=user,
                kind=kind,
                activity_key=activity_key,
                title=title,
                level=level,
                role=role,
                happened_on=happened_on,
                rating_granted=rating_full,
                coins_granted=coins_full,
                confirmed_by=confirmed_by,
                note=note,
            )

    return AwardOutcome(True, res.rating_delta, res.coins_delta)


def award_event(
    user: User,
    *,
    activity_key: str,
    level: str,
    role: str,
    title: str = "",
    happened_on: date | None = None,
    confirmed_by: User | None = None,
    note: str = "",
) -> AwardOutcome:
    """Начисление за мероприятие (раздел 5)."""
    from django.utils import timezone

    return _award_activity(
        user,
        kind=PolozhenieAwardKind.EVENT,
        activity_key=activity_key,
        title=title,
        level=level,
        role=role,
        happened_on=happened_on or timezone.localdate(),
        tariffs=getattr(settings, "POLOZHENIE_EVENT_TARIFFS", {}),
        role_order=tuple(getattr(settings, "POLOZHENIE_EVENT_ROLES", ())),
        levels=tuple(getattr(settings, "POLOZHENIE_EVENT_LEVELS", ())),
        source=RatingChangeSource.EVENT,
        label="Мероприятие",
        confirmed_by=confirmed_by,
        note=note,
    )


def award_olympiad(
    user: User,
    *,
    activity_key: str,
    level: str,
    result: str,
    title: str = "",
    happened_on: date | None = None,
    confirmed_by: User | None = None,
    note: str = "",
) -> AwardOutcome:
    """Начисление за олимпиаду (раздел 6).

    Победителю начисляется награда за победу вместо награды за участие:
    если участие уже учтено, начисляется разница (п. 6.3).
    """
    from django.utils import timezone

    return _award_activity(
        user,
        kind=PolozhenieAwardKind.OLYMPIAD,
        activity_key=activity_key,
        title=title,
        level=level,
        role=result,
        happened_on=happened_on or timezone.localdate(),
        tariffs=getattr(settings, "POLOZHENIE_OLYMPIAD_TARIFFS", {}),
        role_order=tuple(getattr(settings, "POLOZHENIE_OLYMPIAD_RESULTS", ())),
        levels=tuple(getattr(settings, "POLOZHENIE_OLYMPIAD_LEVELS", ())),
        source=RatingChangeSource.OLYMPIAD,
        label="Олимпиада",
        confirmed_by=confirmed_by,
        note=note,
    )


# --- Раздел 7: проекты -------------------------------------------------------


def award_project(
    user: User,
    *,
    activity_key: str,
    result: str,
    title: str = "",
    happened_on: date | None = None,
    confirmed_by: User | None = None,
    note: str = "",
) -> AwardOutcome:
    """Начисление за принятый результат проекта (п. 7.1-7.3).

    Ключ активности — код задания. Одна работа не оплачивается повторно
    и как самостоятельная задача, и как этап, поэтому ключ должен быть
    одинаковым для обоих. Финальная награда за проект оформляется отдельным
    ключом: п. 7.3 разрешает добавлять её к наградам за этапы.
    """
    from django.utils import timezone

    tariffs = getattr(settings, "POLOZHENIE_PROJECT_TARIFFS", {})
    tariff = tariffs.get(result)
    if tariff is None:
        raise UnknownTariff(f"Неизвестный результат проекта: {result}")

    happened_on = happened_on or timezone.localdate()
    rating = Decimal(str(tariff["rating"]))
    coins = Decimal(str(tariff["coins"]))

    with transaction.atomic():
        exists = PolozhenieAward.objects.filter(
            user=user, kind=PolozhenieAwardKind.PROJECT, activity_key=activity_key
        ).exists()
        if exists:
            return AwardOutcome(False, Decimal("0"), Decimal("0"), "already_awarded")

        res = grant(
            user,
            rating=rating,
            coins=coins,
            source=RatingChangeSource.PROJECT,
            source_id=f"project:{activity_key}"[:64],
            reason=f"Проект: {title or activity_key} — {tariff['title']}",
            confirmed_by=confirmed_by,
        )
        if not res.applied:
            return AwardOutcome(False, Decimal("0"), Decimal("0"), res.reason)

        PolozhenieAward.objects.create(
            user=user,
            kind=PolozhenieAwardKind.PROJECT,
            activity_key=activity_key,
            title=title,
            level="",
            role=result,
            happened_on=happened_on,
            rating_granted=rating,
            coins_granted=coins,
            confirmed_by=confirmed_by,
            note=note,
        )
    return AwardOutcome(True, res.rating_delta, res.coins_delta)


# --- Раздел 9: списания ------------------------------------------------------


def absence_penalty_for_day(
    user: User, day: date, *, confirmed_by: User | None = None, note: str = ""
) -> AwardOutcome:
    """Списание за подтверждённые пропуски дня (п. 9.1).

    1 балл за пару, максимум 4 за учебный день, дополнительного штрафа за
    сам день нет. Монеты не списываются (п. 9.4).

    Вызывается только после подтверждения причины тьютором: п. 9.2 запрещает
    применять штраф, пока причина выясняется. Поэтому автоматического
    ежедневного прогона у этой функции нет.
    """
    per_lesson = Decimal(
        str(getattr(settings, "POLOZHENIE_PENALTIES", {}).get("ABSENCE_PER_LESSON", 1))
    )
    daily_max = Decimal(
        str(getattr(settings, "POLOZHENIE_PENALTIES", {}).get("ABSENCE_DAILY_MAX", 4))
    )

    missed = LessonAttendance.objects.filter(
        user=user, lesson_date=day, status=LessonAttendanceStatus.MISSED
    ).count()
    if missed == 0:
        return AwardOutcome(False, Decimal("0"), Decimal("0"), "no_missed_lessons")

    amount = min(per_lesson * missed, daily_max)
    res = grant(
        user,
        rating=-amount,
        coins=0,
        source=RatingChangeSource.PENALTY,
        source_id=f"absence:{day.isoformat()}",
        reason=f"Пропуски {day.isoformat()}: {missed} пар, списано {amount}" + (f". {note}" if note else ""),
        confirmed_by=confirmed_by,
    )
    return AwardOutcome(res.applied, res.rating_delta, res.coins_delta, res.reason)


# --- Пакетное начисление из админки -----------------------------------------
# Положение (п. 5.1) допускает подтверждение участия списком участников,
# и в админке это удобнее всего: выбрал студентов, выбрал тариф, назвал
# мероприятие. Тариф задаётся одной строкой-кодом вида `event:region:speaker`.


def tariff_choices() -> list[tuple[str, str]]:
    """Все тарифы разделов 5-7 одним списком — для выбора в админке."""
    choices: list[tuple[str, str]] = []

    event_levels = tuple(getattr(settings, "POLOZHENIE_EVENT_LEVELS", ()))
    event_roles = tuple(getattr(settings, "POLOZHENIE_EVENT_ROLES", ()))
    role_titles = getattr(settings, "POLOZHENIE_EVENT_ROLE_TITLES", {})
    level_titles = getattr(settings, "POLOZHENIE_EVENT_LEVEL_TITLES", {})
    tariffs = getattr(settings, "POLOZHENIE_EVENT_TARIFFS", {})
    for role in event_roles:
        for level in event_levels:
            rating, coins = tariffs[(role, level)]
            choices.append(
                (
                    f"event:{level}:{role}",
                    f"Мероприятие — {role_titles.get(role, role)}, "
                    f"{level_titles.get(level, level)} ({rating} / {coins})",
                )
            )

    olymp_levels = tuple(getattr(settings, "POLOZHENIE_OLYMPIAD_LEVELS", ()))
    olymp_results = tuple(getattr(settings, "POLOZHENIE_OLYMPIAD_RESULTS", ()))
    result_titles = getattr(settings, "POLOZHENIE_OLYMPIAD_RESULT_TITLES", {})
    olymp_level_titles = getattr(settings, "POLOZHENIE_OLYMPIAD_LEVEL_TITLES", {})
    olymp_tariffs = getattr(settings, "POLOZHENIE_OLYMPIAD_TARIFFS", {})
    for result in olymp_results:
        for level in olymp_levels:
            rating, coins = olymp_tariffs[(result, level)]
            choices.append(
                (
                    f"olympiad:{level}:{result}",
                    f"Олимпиада — {result_titles.get(result, result)}, "
                    f"{olymp_level_titles.get(level, level)} ({rating} / {coins})",
                )
            )

    for code, row in getattr(settings, "POLOZHENIE_PROJECT_TARIFFS", {}).items():
        choices.append(
            (f"project::{code}", f"Проект — {row['title']} ({row['rating']} / {row['coins']})")
        )
    return choices


def parse_tariff_code(code: str) -> tuple[str, str, str]:
    """Разобрать код тарифа на (вид, уровень, роль или результат)."""
    parts = (code or "").split(":")
    if len(parts) != 3 or parts[0] not in {"event", "olympiad", "project"}:
        raise UnknownTariff(f"Неизвестный код тарифа: {code}")
    kind, level, role = parts
    if not role:
        raise UnknownTariff(f"В коде тарифа не указана роль: {code}")
    return kind, level, role


def award_by_tariff_code(
    user: User,
    code: str,
    *,
    activity_key: str,
    title: str = "",
    happened_on: date | None = None,
    confirmed_by: User | None = None,
    note: str = "",
) -> AwardOutcome:
    """Начислить по коду тарифа: единая точка для пакетной выдачи."""
    kind, level, role = parse_tariff_code(code)
    if kind == "event":
        return award_event(
            user,
            activity_key=activity_key,
            level=level,
            role=role,
            title=title,
            happened_on=happened_on,
            confirmed_by=confirmed_by,
            note=note,
        )
    if kind == "olympiad":
        return award_olympiad(
            user,
            activity_key=activity_key,
            level=level,
            result=role,
            title=title,
            happened_on=happened_on,
            confirmed_by=confirmed_by,
            note=note,
        )
    return award_project(
        user,
        activity_key=activity_key,
        result=role,
        title=title,
        happened_on=happened_on,
        confirmed_by=confirmed_by,
        note=note,
    )


def award_bulk_by_tariff_code(
    users,
    code: str,
    *,
    activity_key: str,
    title: str = "",
    happened_on: date | None = None,
    confirmed_by: User | None = None,
    note: str = "",
) -> dict:
    """Начислить списку студентов за одну активность.

    Начисление каждому — за подтверждённый вклад, а не автоматически всей
    команде (п. 7.2), поэтому список составляет ответственный, а не код.
    """
    granted = 0
    skipped = 0
    rating_total = Decimal("0")
    coins_total = Decimal("0")
    for user in users:
        outcome = award_by_tariff_code(
            user,
            code,
            activity_key=activity_key,
            title=title,
            happened_on=happened_on,
            confirmed_by=confirmed_by,
            note=note,
        )
        if outcome.granted:
            granted += 1
            rating_total += outcome.rating
            coins_total += outcome.coins
        else:
            skipped += 1
    return {
        "granted": granted,
        "skipped": skipped,
        "rating": rating_total,
        "coins": coins_total,
    }
