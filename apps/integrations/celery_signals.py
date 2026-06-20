"""Глобальные Celery-сигналы: алерт при падении задач."""

from __future__ import annotations

import logging
import traceback

from celery.signals import task_failure

from apps.integrations.services.telegram_alert import send_alert_to_admin

logger = logging.getLogger(__name__)


@task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback_obj=None, **kw):
    task_name = getattr(sender, "name", None) or str(sender)
    exc = exception or Exception("unknown")
    tb = ""
    if traceback_obj is not None:
        tb = "".join(traceback.format_tb(traceback_obj))
    elif exception is not None:
        tb = traceback.format_exc()

    message = (
        f"Задача: {task_name}\n"
        f"Task ID: {task_id}\n"
        f"Аргументы: {args}\n"
        f"kwargs: {kwargs}\n\n"
        f"Ошибка: {exc}\n\n"
        f"Трассировка:\n{tb}"
    )
    send_alert_to_admin(
        title=f"Ошибка Celery: {task_name}",
        message=message,
        error_type="celery",
        deduplicate_key=f"celery:{task_name}:{type(exc).__name__}",
        is_critical=True,
    )
    logger.error("Celery task failed: %s (%s)", task_name, exc)
