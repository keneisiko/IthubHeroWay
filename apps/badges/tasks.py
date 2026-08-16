"""Периодическая выдача значков."""

from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from apps.accounts.models import Role
from apps.badges.services import award_badges_for_user

logger = logging.getLogger(__name__)


@shared_task
def check_badges_weekly() -> str:
    """Еженедельный прогон условий выдачи значков.

    Задача стояла в расписании с пустым телом: расписание существовало,
    а значки не выдавались никогда — при том, что и модели, и правила выдачи
    в проекте есть.

    Обходим только активированных агентов: значки участвуют в рейтинге,
    а он и так считается только по ним.
    """
    User = get_user_model()
    users = (
        User.objects.filter(role=Role.AGENT, telegram_link__is_active=True)
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
