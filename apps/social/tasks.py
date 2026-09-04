"""Фоновые задачи социальных механик."""

from __future__ import annotations

import logging

from celery import shared_task

from apps.social.services.duels import resolve_due_duels
from apps.social.services.rewards import pay_mentors_weekly

logger = logging.getLogger(__name__)


@shared_task
def resolve_duels() -> dict:
    """Подвести итоги дуэлей, у которых вышел срок.

    Без этой задачи принятая дуэль оставалась активной вечно и блокировала
    обоим участникам любые новые вызовы.
    """
    result = resolve_due_duels()
    logger.info("resolve_duels %s", result)
    return result


@shared_task
def pay_mentorship_weekly() -> dict:
    """Еженедельные монеты наставникам за активных подшефных."""
    result = pay_mentors_weekly()
    logger.info("pay_mentorship_weekly %s", result)
    return result
