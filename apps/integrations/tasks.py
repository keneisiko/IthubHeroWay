from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.integrations.lxp_task_helpers import refresh_lxp_token_sync
from apps.integrations.services.hik_import import import_from_portal
from apps.integrations.services.lxp_snapshot_store import save_snapshot
from apps.integrations.services.hik_attendance_processor import process_unprocessed_hik_events, save_hik_row_as_event
from apps.integrations.services.hik_client import HikCentralClient, HikClientError
from apps.integrations.services.hik_snapshot_service import apply_hik_snapshot
from apps.integrations.services.lxp_graphql_client import LXPGraphQLClient
from apps.integrations.services.telegram_alert import send_alert_to_admin

logger = logging.getLogger(__name__)


def _hik_process_pending(label: str) -> str:
    if not getattr(settings, "HIK_PROCESS_ENABLED", True):
        return "hik_off"
    proc_seen, ext_n, skipped = process_unprocessed_hik_events(
        limit=int(getattr(settings, "HIK_PROCESS_BATCH", 8000))
    )
    return f"{label} processed={proc_seen} external={ext_n} skipped_users={skipped}"


@shared_task
def refresh_lxp_token() -> str:
    # Плановое обновление перед ночным снимком — здесь вход осознанный.
    refresh_lxp_token_sync(force=True)
    return "token_refreshed"


@shared_task
def fetch_lxp_snapshot() -> str:
    yesterday = timezone.now().date() - timedelta(days=1)
    client = LXPGraphQLClient()
    # get_token() сам решает, нужен ли вход: раньше здесь подряд шли
    # refresh_lxp_token_sync() и get_token(), то есть два логина за прогон
    # поверх токена, обновлённого beat-задачей за 15 минут до этого.
    client.get_token()
    data = client.fetch_all_data(date=yesterday)
    _, stored = save_snapshot(yesterday, data)
    if not stored:
        # Пересчитывать рейтинг по данным, которые мы отказались сохранять,
        # нельзя: они хуже уже имеющихся.
        logger.warning("LXP snapshot %s не сохранён: результат хуже существующего", yesterday)
        return f"Snapshot for {yesterday} rejected (worse than stored)"

    from apps.progress.tasks import recalculate_rating_for_date

    recalculate_rating_for_date.delay(yesterday.isoformat())
    logger.info("LXP snapshot saved for %s", yesterday)
    return f"Snapshot for {yesterday} saved"


@shared_task
def fetch_hik_web_daily(target_date_iso: str | None = None) -> str:
    """Забрать проходы из портала по HTTP (основной путь).

    Браузер участвует только в получении cookies. При недоступности прямого
    API падаем на старый сценарий с выгрузкой XLSX, и только если не вышло
    и это — шлём алерт: раньше пустой результат и поломка были неразличимы.
    """
    if getattr(settings, "HIK_DATA_MODE", "snapshot") == "off":
        return "hik_off"

    target = (
        date.fromisoformat(target_date_iso) if target_date_iso else timezone.localdate() - timedelta(days=1)
    )

    try:
        outcome = import_from_portal(target, target)
    except Exception as exc:  # noqa: BLE001 — решение о фолбэке принимаем здесь
        logger.warning("fetch_hik_web_daily: прямой API не сработал (%s), пробую XLSX", exc)
        fallback = fetch_hik_browser_export_daily(target_date_iso=target.isoformat())
        if fallback.startswith("hik_browser_error") or fallback == "hik_browser_disabled":
            send_alert_to_admin(
                title="Импорт проходов Hik не удался",
                message=(
                    f"Дата: {target}\nПрямой API: {exc}\nФолбэк XLSX: {fallback}"
                ),
                error_type="hik",
                deduplicate_key="hik_import_failed",
                is_critical=False,
            )
        return f"hik_web_failed:{exc}; fallback={fallback}"

    run = outcome.run
    return (
        f"hik_web date={target} status={run.status} records={run.records_fetched} "
        f"new={run.events_created} external={run.external_created} unmatched={run.users_unmatched}"
    )


@shared_task
def fetch_hik_events() -> str:
    """
    api: HikCentral → HikEvent.
    browser: Playwright XLSX export с hik-connectru → HikSnapshot → HikEvent.
    snapshot: обработка очереди (данные кладутся через pull_hik_attendance).
    """
    mode = getattr(settings, "HIK_DATA_MODE", "snapshot")
    if mode == "off":
        return "hik_off"
    if mode == "browser":
        return fetch_hik_browser_export_daily()
    if mode == "snapshot":
        return _hik_process_pending("hik_snapshot_mode")

    if not getattr(settings, "HIK_FETCH_ENABLED", False):
        return "hik_api_not_configured"

    client = HikCentralClient()
    window = timedelta(hours=int(getattr(settings, "HIK_FETCH_LOOKBACK_HOURS", 2)))
    end = timezone.now()
    start = end - window
    try:
        rows = client.fetch_event_records_pages(
            start=start,
            end=end,
            page_size=int(getattr(settings, "HIK_PAGE_SIZE", 100)),
        )
    except HikClientError as e:
        logger.warning("fetch_hik_events: HikCentral error %s", e)
        send_alert_to_admin(
            title="Ошибка синхронизации Hik-Connect",
            message=f"fetch_hik_events: {e}",
            error_type="hik",
            deduplicate_key="hik_fetch_events",
            is_critical=False,
        )
        return f"hik_fetch_error:{e}"
    inserted = 0
    seen = 0
    for row in rows:
        seen += 1
        _, created = save_hik_row_as_event(row)
        if created:
            inserted += 1
    proc_msg = _hik_process_pending("hik_api")
    logger.info("fetch_hik_events rows=%s new_db=%s %s", seen, inserted, proc_msg)
    return f"hik_saved={inserted}/{seen} {proc_msg}"


@shared_task
def process_hik_snapshot_daily() -> str:
    """Импорт и обработка Hik за вчера: browser export или существующий HikSnapshot."""
    mode = getattr(settings, "HIK_DATA_MODE", "snapshot")
    if mode == "off":
        return "hik_off"
    yesterday = timezone.localdate() - timedelta(days=1)
    if mode == "browser" or getattr(settings, "HIK_USE_BROWSER_EXPORT", False):
        from apps.integrations.services.hik_browser_export import HikBrowserExportError, fetch_hik_xlsx_for_date
        from apps.integrations.services.hik_browser_import import import_hik_export_file
        from apps.integrations.services.hik_browser_settings import hik_browser_config_from_settings

        config = hik_browser_config_from_settings()
        if not config.email or not config.password:
            return "hik_browser_missing_credentials"
        try:
            path = fetch_hik_xlsx_for_date(config, yesterday)
            result = import_hik_export_file(path, yesterday, skip_process=False)
        except HikBrowserExportError as e:
            send_alert_to_admin(
                title="Ошибка nightly Hik browser export",
                message=str(e),
                error_type="hik",
                deduplicate_key="hik_browser_nightly",
                is_critical=False,
            )
            return f"hik_browser_error:{e}"
        return (
            f"hik_browser_nightly date={yesterday} import={result.get('import_inserted')} "
            f"external={result.get('external_created')}"
        )

    result = apply_hik_snapshot(yesterday, skip_process=False)
    if result.get("error"):
        return f"hik_snapshot_missing:{yesterday.isoformat()}"
    return (
        f"hik_snapshot date={yesterday} import={result.get('import_inserted')} "
        f"external={result.get('external_created')}"
    )


@shared_task
def process_hik_events_daily() -> str:
    """Доработка очереди необработанных HikEvent."""
    if not getattr(settings, "HIK_PROCESS_ENABLED", True):
        return "hik_off"
    proc_seen, ext_n, skipped = process_unprocessed_hik_events(limit=50_000)
    return f"hik_daily processed={proc_seen} external={ext_n} skipped_users={skipped}"


@shared_task
def process_late_events() -> str:
    """Обработка HikEvent: опоздания, ExternalEvent, штрафы рейтинга."""
    return _hik_process_pending("hik_late")


@shared_task
def fetch_hik_browser_export_daily(target_date_iso: str | None = None) -> str:
    """Скачать XLSX с Hik Connect и импортировать в пайплайн Hik.

    Фолбэк на случай, когда прямой HTTP-путь недоступен. Дата задаётся явно,
    чтобы фолбэк забирал тот же день, что и основная задача.
    """
    from apps.integrations.services.hik_browser_export import HikBrowserExportError, fetch_hik_xlsx_for_date
    from apps.integrations.services.hik_browser_import import import_hik_export_file
    from apps.integrations.services.hik_browser_settings import hik_browser_config_from_settings

    if getattr(settings, "HIK_DATA_MODE", "") not in {"browser"} and not getattr(
        settings, "HIK_USE_BROWSER_EXPORT", False
    ):
        return "hik_browser_disabled"

    target = date.fromisoformat(target_date_iso) if target_date_iso else timezone.localdate()
    config = hik_browser_config_from_settings()
    if not config.email or not config.password:
        return "hik_browser_missing_credentials"
    try:
        path = fetch_hik_xlsx_for_date(config, target)
        result = import_hik_export_file(path, target, skip_process=False)
    except HikBrowserExportError as e:
        logger.warning("fetch_hik_browser_export_daily: %s", e)
        send_alert_to_admin(
            title="Ошибка выгрузки Hik Connect (browser)",
            message=str(e),
            error_type="hik",
            deduplicate_key="hik_browser_export",
            is_critical=False,
        )
        return f"hik_browser_error:{e}"
    return (
        f"hik_browser date={target.isoformat()} file={path.name} "
        f"import={result.get('import_inserted')} external={result.get('external_created')}"
    )
