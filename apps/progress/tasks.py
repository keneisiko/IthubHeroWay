from celery import shared_task
from datetime import date
from django.utils.dateparse import parse_date
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
def recalculate_rating_for_date(date_iso: str) -> str:
    """
    Пересчёт рейтинга на основе данных LXP snapshot за указанную дату.
    """
    target_date = parse_date(date_iso)
    if not target_date:
        return f"invalid_date:{date_iso}"
    from apps.progress.services.lxp_rating_from_snapshot import apply_rating_from_lxp_snapshot

    result = apply_rating_from_lxp_snapshot(target_date)
    return (
        f"lxp_rating:{target_date.isoformat()}:considered={result.users_considered}"
        f":updated={result.users_updated}:partial={result.partial_snapshot}:{result.notes}"
    )


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

