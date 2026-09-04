"""Дуэли: вызов, принятие и подведение итога.

Раньше механики не было вовсе: вызов создавался, принятие меняло статус —
и на этом всё. Победителя никто не определял, ставка `DUEL_BET` не
использовалась нигде, а принятая дуэль навсегда оставалась «активной»
и блокировала обоим участникам любые новые вызовы.

Правило простое и проверяемое: побеждает тот, кто за срок дуэли прибавил
больше рейтинга. Стартовые значения фиксируются в момент принятия — иначе
сравнивать было бы не с чем.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.notifications.services import events
from apps.social.models import Duel, DuelStatus


class DuelNotAllowed(ValueError):
    pass


def _limits() -> dict:
    return getattr(settings, "RATING_LIMITS", {})


def duel_bet() -> int:
    return int(_limits().get("DUEL_BET", 5))


def duel_duration_days() -> int:
    return int(_limits().get("DUEL_DURATION_DAYS", 7))


def invite_ttl_days() -> int:
    return int(_limits().get("DUEL_INVITE_TTL_DAYS", 3))


def active_duels_q() -> Q:
    """Дуэли, которые занимают участника: приглашение или идущий поединок."""
    return Q(status=DuelStatus.PENDING) | Q(status=DuelStatus.ACCEPTED, resolved_at__isnull=True)


def duels_for(user) -> list[Duel]:
    return list(
        Duel.objects.filter(Q(challenger=user) | Q(opponent=user))
        .select_related("challenger", "opponent", "winner")
        .order_by("-created_at")[:50]
    )


@transaction.atomic
def accept_duel(user, duel_id: int) -> Duel:
    """Принять вызов: фиксируем стартовые рейтинги и срок подведения итога."""
    duel = Duel.objects.select_for_update().filter(pk=duel_id, opponent=user).first()
    if not duel:
        raise DuelNotAllowed("Вызов не найден.")
    if duel.status != DuelStatus.PENDING:
        raise DuelNotAllowed("На этот вызов уже ответили.")

    now = timezone.now()
    duel.status = DuelStatus.ACCEPTED
    duel.accepted_at = now
    duel.challenger_rating_start = duel.challenger.rating_current
    duel.opponent_rating_start = duel.opponent.rating_current
    duel.resolve_after = now + timedelta(days=duel_duration_days())
    duel.bet_coins = duel_bet()
    duel.save(
        update_fields=[
            "status",
            "accepted_at",
            "challenger_rating_start",
            "opponent_rating_start",
            "resolve_after",
            "bet_coins",
        ]
    )
    return duel


@transaction.atomic
def reject_duel(user, duel_id: int) -> Duel:
    duel = Duel.objects.select_for_update().filter(pk=duel_id, opponent=user).first()
    if not duel:
        raise DuelNotAllowed("Вызов не найден.")
    if duel.status != DuelStatus.PENDING:
        raise DuelNotAllowed("На этот вызов уже ответили.")

    duel.status = DuelStatus.REJECTED
    duel.resolved_at = timezone.now()
    duel.save(update_fields=["status", "resolved_at"])
    return duel


@transaction.atomic
def cancel_duel(user, duel_id: int) -> Duel:
    """Отозвать свой вызов, пока на него не ответили."""
    duel = Duel.objects.select_for_update().filter(pk=duel_id, challenger=user).first()
    if not duel:
        raise DuelNotAllowed("Вызов не найден.")
    if duel.status != DuelStatus.PENDING:
        raise DuelNotAllowed("Вызов уже нельзя отозвать.")

    duel.status = DuelStatus.REJECTED
    duel.resolved_at = timezone.now()
    duel.save(update_fields=["status", "resolved_at"])
    return duel


@transaction.atomic
def resolve_duel(duel: Duel, *, now=None) -> Duel:
    """Подвести итог: победитель забирает ставку проигравшего.

    Ничья ничего не меняет — это честнее, чем присуждать победу
    по случайному признаку вроде того, кто вызвал.
    """
    now = now or timezone.now()
    duel = Duel.objects.select_for_update().get(pk=duel.pk)
    if duel.status != DuelStatus.ACCEPTED or duel.resolved_at:
        return duel

    challenger = User.objects.select_for_update().get(pk=duel.challenger_id)
    opponent = User.objects.select_for_update().get(pk=duel.opponent_id)

    challenger_gain = challenger.rating_current - int(duel.challenger_rating_start or 0)
    opponent_gain = opponent.rating_current - int(duel.opponent_rating_start or 0)

    winner = None
    loser = None
    if challenger_gain > opponent_gain:
        winner, loser = challenger, opponent
    elif opponent_gain > challenger_gain:
        winner, loser = opponent, challenger

    bet = int(duel.bet_coins or duel_bet())
    if winner and loser:
        # Списываем у проигравшего столько, сколько у него есть: уходить
        # в минус по монетам нельзя, а отменять итог из-за пустого кошелька —
        # значит поощрять тех, кто всё потратил перед подведением итога.
        taken = min(bet, loser.coins_balance)
        if taken:
            loser.coins_balance -= taken
            loser.save(update_fields=["coins_balance"])
            # Победителю ровно столько же и без дневного лимита: ставка —
            # это перевод между студентами, а не заработок. С лимитом монеты
            # исчезали бы из системы: у проигравшего списали, победителю
            # не начислили.
            winner.coins_balance += taken
            winner.save(update_fields=["coins_balance"])
        duel.winner = winner

    duel.status = DuelStatus.FINISHED
    duel.resolved_at = now
    duel.save(update_fields=["status", "resolved_at", "winner"])

    # Уведомление после сохранения: если Telegram недоступен, итог всё равно
    # зафиксирован.
    transaction.on_commit(lambda: events.duel_resolved(duel))
    return duel


def resolve_due_duels(now=None) -> dict:
    """Подвести итоги дуэлям, у которых вышел срок, и снять протухшие вызовы."""
    now = now or timezone.now()
    resolved = 0
    for duel in Duel.objects.filter(
        status=DuelStatus.ACCEPTED, resolved_at__isnull=True, resolve_after__lte=now
    ).select_related("challenger", "opponent"):
        resolve_duel(duel, now=now)
        resolved += 1

    # Неотвеченные вызовы не должны висеть вечно: они блокируют участникам
    # новые дуэли.
    expired = Duel.objects.filter(
        status=DuelStatus.PENDING, created_at__lte=now - timedelta(days=invite_ttl_days())
    ).update(status=DuelStatus.REJECTED, resolved_at=now)

    return {"resolved": resolved, "expired_invites": expired}


def duel_wins(user) -> int:
    return Duel.objects.filter(winner=user).count()
