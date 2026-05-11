from celery import shared_task
from apps.progress.services.characteristics import update_all_characteristics
from apps.integrations.services.lxp_client import LXPClient
from apps.integrations.models import ExternalEvent
from django.db import IntegrityError


@shared_task
def recalculate_rating_daily() -> None:
    """
    Ежедневный пересчёт рейтинга (06:00) на основе данных из LXP/YouGile.
    В реальной реализации здесь будет интеграция с apps.integrations и моделями progress.
    """
    snapshot = LXPClient().fetch_daily_snapshot()
    for event in snapshot.get("events", []):
        external_id = str(event.get("id") or "")
        if not external_id:
            continue
        try:
            ExternalEvent.objects.create(source="lxp", external_event_id=external_id, payload=event)
        except IntegrityError:
            continue
    return None


@shared_task
def recalculate_pillars_weekly() -> None:
    """
    Еженедельный пересчёт характеристик (воскресенье 22:00).
    """
    update_all_characteristics()
    return None


@shared_task
def check_strikes_daily() -> None:
    """
    Ежедневная проверка серий (23:00) и начисление бонусов.
    """
    # TODO: реализовать проверку серий и бонусы
    return None

