"""Периодическая выдача значков."""

from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from apps.accounts.models import Role
from apps.badges.services import award_badges_for_user
from apps.integrations.services.account_gate import agents_for_scoring
from apps.operations.services.platform_settings import accruals_enabled

logger = logging.getLogger(__name__)


@shared_task
def check_badges_weekly() -> str:
    """Прогон условий выдачи нашивок — каждый вечер (имя историческое).

    Задача стояла в расписании с пустым телом: расписание существовало,
    а значки не выдавались никогда — при том, что и модели, и правила выдачи
    в проекте есть.

    Аудитория та же, что у остальных начислений — `agents_for_scoring`.
    Прежде здесь стоял свой фильтр по привязке Telegram, и студент без
    привязки получал монеты за учёбу, но не получал нашивок: правило
    «кому начисляем» должно жить в одном месте.
    """
    if not accruals_enabled():
        return "accruals_disabled"

    User = get_user_model()
    users = (
        agents_for_scoring(User.objects.filter(role=Role.AGENT))
        .only("id", "username", "coins_balance")
        .order_by("id")
    )

    checked = 0
    awarded = 0
    errors = 0

    for user in users.iterator(chunk_size=200):
        checked += 1
        try:
            awarded += len(award_badges_for_user(user))
        except Exception:
            errors += 1
            logger.exception("badge_award_failed user=%s", user.pk)

    logger.info("check_badges_weekly checked=%s awarded=%s errors=%s", checked, awarded, errors)
    return f"checked={checked} awarded={awarded} errors={errors}"
