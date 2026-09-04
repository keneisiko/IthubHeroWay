"""Тексты и адресаты уведомлений по событиям платформы.

Отдельный слой поверх отправки: вьюхам и сервисам незачем знать формулировки,
а формулировкам — способ доставки. Здесь же решается, кому именно писать.

Все функции возвращают число доставленных сообщений и никогда не бросают
исключений: уведомление — побочный эффект, из-за которого нельзя ронять
действие, которое его вызвало.
"""

from __future__ import annotations

import logging

from apps.accounts.models import Role, User
from apps.notifications.services.telegram import notify_user, notify_users

logger = logging.getLogger(__name__)


def _name(user) -> str:
    return user.callsign or user.username


def _safe(fn, *args, **kwargs) -> int:
    try:
        return fn(*args, **kwargs)
    except Exception:  # noqa: BLE001 — уведомление не должно валить операцию
        logger.exception("Не удалось отправить уведомление")
        return 0


def duel_invited(duel) -> int:
    """Сопернику: пришёл вызов. Без этого о вызове не узнавали вовсе."""
    text = (
        f"⚔️ {_name(duel.challenger)} вызывает вас на дуэль.\n"
        f"Ставка: {duel.bet_coins or 0} монет.\n"
        "Принять или отклонить — в профиле на платформе."
    )
    return _safe(notify_user, duel.opponent, text)


def duel_answered(duel, *, accepted: bool) -> int:
    """Инициатору: на его вызов ответили."""
    if accepted:
        deadline = duel.resolve_after.strftime("%d.%m.%Y") if duel.resolve_after else ""
        text = (
            f"⚔️ {_name(duel.opponent)} принял вызов.\n"
            f"Побеждает тот, кто прибавит больше рейтинга к {deadline}."
        )
    else:
        text = f"⚔️ {_name(duel.opponent)} отклонил вызов."
    return _safe(notify_user, duel.challenger, text)


def duel_resolved(duel) -> int:
    """Обоим: итог дуэли."""
    sent = 0
    if duel.winner_id:
        loser = duel.opponent if duel.winner_id == duel.challenger_id else duel.challenger
        sent += _safe(
            notify_user,
            duel.winner,
            f"🏆 Вы выиграли дуэль у {_name(loser)}: +{duel.bet_coins} монет.",
        )
        sent += _safe(
            notify_user,
            loser,
            f"⚔️ Дуэль с {_name(duel.winner)} проиграна: −{duel.bet_coins} монет.",
        )
    else:
        text = "⚔️ Дуэль завершилась ничьёй: ставки остались при своих."
        sent += _safe(notify_users, [duel.challenger, duel.opponent], text)
    return sent


def respect_received(respect, coins: int) -> int:
    text = f"👏 {_name(respect.from_user)} отправил вам респект"
    if coins:
        text += f": +{coins} монет"
    if respect.message:
        text += f"\n«{respect.message}»"
    return _safe(notify_user, respect.to_user, text)


def mentorship_started(mentorship) -> int:
    """Подшефному: у него появился наставник."""
    text = (
        f"🤝 {_name(mentorship.mentor)} стал вашим наставником.\n"
        "Обращайтесь с вопросами по учёбе."
    )
    return _safe(notify_user, mentorship.mentee, text)


def proof_submitted(proof) -> int:
    """Кураторам отряда: пришла заявка на проверку.

    Иначе заявка лежит в админке, пока кто-нибудь случайно не заглянет.
    """
    squad_id = proof.user.squad_id
    if not squad_id:
        return 0
    curators = User.objects.filter(role=Role.CURATOR, squad_id=squad_id)
    text = (
        f"📝 {_name(proof.user)} отправил подтверждение по квесту «{proof.quest.title}».\n"
        "Проверить: раздел «Подтверждения выполнения» в админке."
    )
    return _safe(notify_users, curators, text)


def proof_reviewed(proof, *, approved: bool) -> int:
    """Студенту: заявку посмотрели."""
    if approved:
        text = f"✅ Квест «{proof.quest.title}» подтверждён — награда начислена."
    else:
        text = (
            f"❌ Подтверждение по квесту «{proof.quest.title}» отклонено.\n"
            "Можно приложить другую ссылку и отправить заново."
        )
    return _safe(notify_user, proof.user, text)
