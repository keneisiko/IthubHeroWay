"""Рейтинг из снимка LXP: событийная годовая модель.

Раньше сервис каждый день заново оценивал текущее состояние: +20 за каждую
закрытую тему и −20 за каждую открытую. Одно и то же положение дел
пересчитывалось ежедневно, поэтому студент с двенадцатью открытыми темами
терял по 20 в день просто за то, что семестр только начался, а отличник
упирался в потолок 1000 за полторы недели.

Теперь начисляется только изменение между снимками:

* тема перешла из открытой в закрытую → плюс, один раз за тему;
* тема висит открытой дольше `TOPIC_STALE_DAYS` → минус, один раз за тему;
* просто открытая тема, срок которой не вышел, не стоит ничего.

Стоимость темы нормирована по курсу (см. `course_norm`), поэтому курсы
с разным объёмом программы имеют сопоставимый годовой максимум.

Эвристики статусов — в `apps.progress.services.ct_status`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.integrations.models import LXPSnapshot
from apps.integrations.services.lxp_snapshot_format import unwrap_category
from apps.progress.models import LXPTopicState, RatingChangeSource, RatingLog
from apps.progress.services.academic_year import academic_year_label
from apps.progress.services.course_norm import observe_course_volume, points_per_topic
from apps.progress.services.ct_status import iter_user_topics

logger = logging.getLogger(__name__)

RATING_FLOOR = 0
RATING_CEILING = 1000


@dataclass(frozen=True)
class LxpRatingApplyResult:
    snapshot_date: date
    users_considered: int
    users_updated: int
    partial_snapshot: bool
    notes: str


@dataclass
class _UserOutcome:
    closed_now: int = 0
    stale_now: int = 0
    open_total: int = 0
    stale_total: int = 0
    delta_positive: int = 0
    delta_negative: int = 0
    all_closed_bonus: int = 0


def _cfg() -> dict:
    return getattr(settings, "RATING_YEAR", {})


def _bonus_already_applied(user_id: int, source_id: str) -> bool:
    return RatingLog.objects.filter(user_id=user_id, source_id=source_id).exists()


def _already_applied_user_ids(snapshot_date: date) -> set[int]:
    """Кому дельта за эту дату уже начислена.

    Состояние тем само по себе идемпотентно — второй проход не увидит
    переходов. Но проверка по журналу дешевле и оставляет понятный след.
    """
    return set(
        RatingLog.objects.filter(source_id=snapshot_date.isoformat()).values_list("user_id", flat=True)
    )


def _apply_topic_transitions(
    state: LXPTopicState,
    current: dict[str, bool],
    snapshot_date: date,
    per_topic_points: int,
    stale_days: int,
    stale_penalty: int,
) -> _UserOutcome:
    """Сравнить снимок с сохранённым состоянием и посчитать дельту."""
    outcome = _UserOutcome()
    stored: dict = state.topics if isinstance(state.topics, dict) else {}
    updated: dict = {}

    for key, closed in current.items():
        previous = stored.get(key) if isinstance(stored.get(key), dict) else None

        if closed:
            was_open = previous is not None and not previous.get("closed")
            if was_open:
                outcome.closed_now += 1
                outcome.delta_positive += per_topic_points
            updated[key] = {"closed": True, "since": snapshot_date.isoformat(), "penalized": False}
            continue

        outcome.open_total += 1

        # Тема, открывшаяся заново после закрытия, начинает отсчёт срока с нуля.
        since_raw = None
        penalized = False
        if previous is not None and not previous.get("closed"):
            since_raw = previous.get("since")
            penalized = bool(previous.get("penalized"))

        since = snapshot_date.isoformat() if not since_raw else str(since_raw)
        try:
            since_date = date.fromisoformat(since)
        except ValueError:
            since_date = snapshot_date
            since = snapshot_date.isoformat()

        if (snapshot_date - since_date).days > stale_days:
            outcome.stale_total += 1
            if not penalized:
                outcome.stale_now += 1
                outcome.delta_negative += stale_penalty
                penalized = True

        updated[key] = {"closed": False, "since": since, "penalized": penalized}

    state.topics = updated
    state.last_snapshot_date = snapshot_date
    return outcome


def _seed_baseline(user, state: LXPTopicState, current: dict[str, bool], snapshot_date: date) -> None:
    """Зафиксировать первый снимок без начислений.

    Начислять за темы, закрытые до подключения системы, значило бы выдать
    рейтинг задним числом — причём тем больше, чем старше курс.
    """
    state.topics = {
        key: {"closed": bool(closed), "since": snapshot_date.isoformat(), "penalized": False}
        for key, closed in current.items()
    }
    state.last_snapshot_date = snapshot_date
    state.baseline_done = True
    state.save(update_fields=["topics", "last_snapshot_date", "baseline_done", "updated_at"])
    # Нулевая запись журнала за эту дату: без неё повторный прогон того же дня
    # считался бы первым «настоящим» и мог что-то начислить.
    RatingLog.objects.get_or_create(
        user=user,
        source_id=snapshot_date.isoformat(),
        defaults={
            "value_before": user.rating_current,
            "value_after": user.rating_current,
            "delta": 0,
            "source": RatingChangeSource.SYSTEM,
            "reason": f"LXP {snapshot_date.isoformat()}: зафиксировано исходное состояние тем",
        },
    )


def apply_rating_from_lxp_snapshot(
    snapshot_date: date,
    *,
    snapshot_row: LXPSnapshot | None = None,
    force: bool = False,
) -> LxpRatingApplyResult:
    cfg = _cfg()
    kp = getattr(settings, "RATING_KP", {})
    limits = getattr(settings, "RATING_LIMITS", {})

    snap = snapshot_row or LXPSnapshot.objects.filter(date=snapshot_date).first()
    if not snap:
        return LxpRatingApplyResult(
            snapshot_date=snapshot_date,
            users_considered=0,
            users_updated=0,
            partial_snapshot=False,
            notes="no_snapshot_row",
        )

    raw = snap.data or {}
    meta = raw.get("meta") or {}
    partial = bool(meta.get("partial"))

    ct_block = raw.get("control_points")
    ct_ok = bool(ct_block.get("ok")) if isinstance(ct_block, dict) else False
    ct_data = unwrap_category(ct_block)

    if not ct_ok:
        # Без данных по темам сравнивать не с чем. Раньше в этом случае всё
        # равно применялся штраф за посещаемость — теперь снимок без КТ
        # просто ничего не меняет.
        return LxpRatingApplyResult(
            snapshot_date=snapshot_date,
            users_considered=0,
            users_updated=0,
            partial_snapshot=partial,
            notes="control_points_not_ok",
        )

    stale_days = int(cfg.get("TOPIC_STALE_DAYS", 30))
    stale_penalty = int(cfg.get("STALE_PENALTY_PER_TOPIC", -20))
    block_threshold = int(cfg.get("STALE_BLOCK_THRESHOLD", 2))
    bonus_cooldown = int(cfg.get("ALL_CLOSED_BONUS_COOLDOWN_DAYS", 30))
    max_when_blocked = int(limits.get("MAX_RATING_WHEN_BLOCKED", 399))
    all_closed_bonus_value = int(kp.get("CT_ALL_CLOSED_BONUS", 30))

    qs = (
        User.objects.filter(telegram_link__is_active=True)
        .exclude(Q(lxp_user_id__isnull=True) | Q(lxp_user_id=""))
        .select_related("squad")
    )

    # Сначала объёмы по курсам: цена темы должна учитывать сегодняшний снимок
    # целиком, иначе первый обработанный студент курса задавал бы норму всем.
    for user in qs.iterator(chunk_size=200):
        per_user = ct_data.get((user.lxp_user_id or "").strip())
        if isinstance(per_user, dict) and per_user:
            observe_course_volume(
                user.squad.course if user.squad else None,
                sum(1 for _ in iter_user_topics(per_user)),
            )

    considered = 0
    updated = 0
    baselines = 0
    skipped_already_applied = 0
    already_applied = set() if force else _already_applied_user_ids(snapshot_date)
    year_label = academic_year_label(snapshot_date)

    for user in qs.iterator(chunk_size=200):
        lxp_uid = (user.lxp_user_id or "").strip()
        if not lxp_uid:
            continue
        per_user = ct_data.get(lxp_uid)
        if not isinstance(per_user, dict) or not per_user:
            continue

        considered += 1
        if user.pk in already_applied:
            skipped_already_applied += 1
            continue

        current = dict(iter_user_topics(per_user))
        if not current:
            continue

        with transaction.atomic():
            state, _ = LXPTopicState.objects.select_for_update().get_or_create(user=user)

            if not state.baseline_done:
                _seed_baseline(user, state, current, snapshot_date)
                baselines += 1
                continue

            per_topic_points = points_per_topic(user.squad.course if user.squad else None)
            outcome = _apply_topic_transitions(
                state, current, snapshot_date, per_topic_points, stale_days, stale_penalty
            )

            bonus_source = f"ct_all_closed:{year_label}"
            if outcome.open_total == 0 and not _bonus_already_applied(user.pk, bonus_source):
                recent = RatingLog.objects.filter(
                    user_id=user.pk,
                    source_id__startswith="ct_all_closed:",
                    created_at__date__gte=snapshot_date - timedelta(days=bonus_cooldown),
                ).exists()
                if not recent:
                    outcome.all_closed_bonus = all_closed_bonus_value

            positive = outcome.delta_positive + outcome.all_closed_bonus
            negative = outcome.delta_negative

            u = User.objects.select_for_update().get(pk=user.pk)
            before = int(u.rating_current)
            blocked = outcome.stale_total >= block_threshold

            # Блокировка запрещает рост, но больше не срезает накопленное:
            # рейтинг копится за год, и обнулять вклад прошлых месяцев из-за
            # двух зависших тем нечестно. Штрафы при этом применяются.
            if blocked:
                positive = min(positive, max(0, max_when_blocked - before))

            delta = positive + negative
            after = max(RATING_FLOOR, min(RATING_CEILING, before + delta))
            stale_total = min(outcome.stale_total, 65535)

            if after == before and stale_total == user.unclosed_ct_count:
                state.save(update_fields=["topics", "last_snapshot_date", "updated_at"])
                continue

            u.unclosed_ct_count = stale_total
            u.rating_current = after
            u.save(update_fields=["unclosed_ct_count", "rating_current"])
            state.save(update_fields=["topics", "last_snapshot_date", "updated_at"])

            reason = "; ".join(
                [
                    f"LXP {snapshot_date.isoformat()} ({year_label})",
                    f"delta={after - before}",
                    f"closed={outcome.closed_now}x{per_topic_points}",
                    f"stale_new={outcome.stale_now}/{outcome.stale_total}",
                    f"bonus={outcome.all_closed_bonus}",
                    f"blocked={blocked}",
                ]
            )[:250]

            RatingLog.objects.create(
                user=u,
                value_before=before,
                value_after=after,
                delta=after - before,
                source=RatingChangeSource.SYSTEM,
                source_id=snapshot_date.isoformat(),
                reason=reason,
            )
            if outcome.all_closed_bonus:
                RatingLog.objects.get_or_create(
                    user=u,
                    source_id=bonus_source,
                    defaults={
                        "value_before": after,
                        "value_after": after,
                        "delta": 0,
                        "source": RatingChangeSource.SYSTEM,
                        "reason": f"Маркер: все КТ закрыты ({year_label})",
                    },
                )
            updated += 1

    notes = (
        f"control_points_ok=True partial_meta={partial} baselines={baselines} "
        f"already_applied={skipped_already_applied}"
    )
    logger.info(
        "lxp_rating_apply date=%s considered=%s updated=%s %s",
        snapshot_date,
        considered,
        updated,
        notes,
    )

    return LxpRatingApplyResult(
        snapshot_date=snapshot_date,
        users_considered=considered,
        users_updated=updated,
        partial_snapshot=partial,
        notes=notes,
    )
