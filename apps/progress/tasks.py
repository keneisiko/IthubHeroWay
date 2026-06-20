from celery import shared_task
from django.db import DatabaseError, IntegrityError
from django.utils.dateparse import parse_date

from apps.integrations.models import ExternalEvent
from apps.integrations.services.lxp_client import LXPClient
from apps.integrations.services.telegram_alert import send_alert_to_admin
from apps.operations.services.health_monitor import monitor_health_and_alert_sync
from apps.progress.services.characteristics import update_all_characteristics
from apps.progress.services.strike_bonuses import apply_strike_bonuses


@shared_task
def recalculate_rating_daily() -> None:
    """
    Ежедневный пересчёт рейтинга (06:00) на основе данных из LXP/YouGile.
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
    """Пересчёт рейтинга на основе данных LXP snapshot за указанную дату."""
    target_date = parse_date(date_iso)
    if not target_date:
        return f"invalid_date:{date_iso}"
    from apps.progress.services.lxp_rating_from_snapshot import apply_rating_from_lxp_snapshot

    try:
        result = apply_rating_from_lxp_snapshot(target_date)
    except (IntegrityError, DatabaseError) as e:
        send_alert_to_admin(
            title="Ошибка применения рейтинга из LXP",
            message=f"Дата: {date_iso}\n{e}",
            error_type="rating",
            deduplicate_key=f"rating_apply:{date_iso}",
            is_critical=False,
        )
        raise
    return (
        f"lxp_rating:{target_date.isoformat()}:considered={result.users_considered}"
        f":updated={result.users_updated}:partial={result.partial_snapshot}:{result.notes}"
    )


@shared_task
def recalculate_pillars_weekly() -> None:
    """Еженедельный пересчёт характеристик (воскресенье 22:00)."""
    update_all_characteristics()
    return None


@shared_task
def check_strikes_daily() -> str:
    """Ежедневная проверка серий и начисление бонусов."""
    result = apply_strike_bonuses()
    return (
        f"strikes:{result['date']}:updated={result['strikes_updated']}"
        f":bonuses={result['bonuses_applied']}"
    )


@shared_task
def apply_strike_bonuses_daily() -> str:
    """Алиас для явного расписания Celery Beat."""
    return check_strikes_daily()


@shared_task
def monitor_health_and_alert() -> str:
    """Периодическая проверка db/redis/celery/lxp token с алертами."""
    result = monitor_health_and_alert_sync()
    return f"health issues={len(result['issues'])} alerts={result['alerts_sent']}"
