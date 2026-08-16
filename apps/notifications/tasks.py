"""Периодические уведомления.

Обе задачи ниже — заглушки. Они намеренно убраны из `CELERY_BEAT_SCHEDULE`:
пока тела нет, расписание создаёт видимость работающих рассылок, которых
не существует. Возвращать в расписание — вместе с реализацией.

Что нужно решить перед реализацией (вопросы к заказчику, а не к коду):
* куда шлём — в личку студенту, в чат отряда или куратору;
* что считается «рисковым студентом» — порог рейтинга, число незакрытых КТ,
  пропуски или их сочетание;
* нужна ли возможность отписаться.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def squad_digest_friday() -> str:
    """Пятничный дайджест отряда — не реализован."""
    logger.warning("squad_digest_friday вызвана, но не реализована")
    return "not_implemented"


@shared_task
def curator_report_monday() -> str:
    """Понедельничный отчёт кураторам — не реализован."""
    logger.warning("curator_report_monday вызвана, но не реализована")
    return "not_implemented"
