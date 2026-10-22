from celery import shared_task
from django.db import DatabaseError, IntegrityError
from django.utils.dateparse import parse_date

from apps.integrations.services.telegram_alert import send_alert_to_admin
from apps.operations.services.health_monitor import monitor_health_and_alert_sync
from apps.operations.services.platform_settings import accruals_enabled
from apps.progress.services.characteristics import update_all_characteristics
from apps.progress.services.strike_bonuses import apply_strike_bonuses


@shared_task
def recalculate_rating_for_date(date_iso: str, force: bool = False) -> str:
    """Пересчёт рейтинга на основе данных LXP snapshot за указанную дату.

    По умолчанию идемпотентен: пользователи, которым дельта за эту дату уже
    начислена, пропускаются. `force=True` — осознанный повторный пересчёт.
    """
    target_date = parse_date(date_iso)
    if not target_date:
        return f"invalid_date:{date_iso}"
    from apps.progress.services.lxp_rating_from_snapshot import apply_rating_from_lxp_snapshot

    try:
        result = apply_rating_from_lxp_snapshot(target_date, force=force)
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
def recalculate_pillars_weekly() -> str:
    """Еженедельный пересчёт характеристик (воскресенье 22:00).

    До запуска не считаем: после обнуления пятиугольники у всех пустые, и
    воскресный пересчёт заполнил бы их по данным LXP и Hik до старта сезона.
    """
    if not accruals_enabled():
        return "accruals_disabled"
    update_all_characteristics()
    return "ok"


@shared_task
def check_strikes_daily() -> str:
    """Ежедневная проверка серий и начисление бонусов."""
    if not accruals_enabled():
        return "accruals_disabled"
    result = apply_strike_bonuses()
    if not result.get("strikes_updated") and result.get("skipped"):
        return f"strikes:{result['date']}:skipped={result['skipped']}"
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


@shared_task(bind=True, max_retries=3)
def accrue_polozhenie_week(self, day_iso: str | None = None) -> str:
    """Недельные начисления по Положению: учёба (раздел 3) и роли (раздел 4).

    Запускается в понедельник за *прошедшую* неделю: данные о посещаемости
    за пятницу приходят ночной загрузкой отметок, и считать неделю в её
    последний день значило бы терять последний учебный день.

    Повтор при сбое безопасен: начисление идемпотентно по ключу периода,
    второй прогон той же недели ничего не удвоит (п. 2.4).
    """
    from datetime import timedelta

    from django.utils import timezone

    # До запуска неделю не считаем и ничего не помечаем оплаченной: ключ
    # периода записывается в журнал только вместе с начислением.
    if not accruals_enabled():
        return "accruals_disabled"

    from apps.progress.services.polozhenie_academic import run_weekly_accrual
    from apps.progress.services.polozhenie_awards import run_weekly_roles

    if day_iso:
        day = parse_date(day_iso)
        if not day:
            return f"invalid_date:{day_iso}"
    else:
        day = timezone.localdate() - timedelta(days=7)

    try:
        academic = run_weekly_accrual(day)
        roles = run_weekly_roles(day)
    except (IntegrityError, DatabaseError) as exc:
        send_alert_to_admin(
            title="Сбой недельного начисления по Положению",
            message=f"Неделя: {day.isoformat()}\n{exc}",
            error_type="rating",
            deduplicate_key=f"polozhenie_week:{day.isoformat()}",
            is_critical=True,
        )
        raise self.retry(exc=exc, countdown=30 * 60) from exc

    return (
        f"polozhenie:{academic.period}"
        f":considered={academic.users_considered}:paid={academic.users_paid}"
        f":rating={academic.rating_total}:coins={academic.coins_total}"
        f":deferred_ct={academic.deferred_ct}:deferred_att={academic.deferred_attendance}"
        f":roles_paid={roles['paid']}"
    )
