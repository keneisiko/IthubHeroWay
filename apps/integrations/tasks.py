from __future__ import annotations

import logging
from datetime import timedelta

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.integrations.lxp_task_helpers import refresh_lxp_token_sync
from apps.integrations.models import LXPSnapshot
from apps.integrations.services.hik_attendance_processor import process_unprocessed_hik_events, save_hik_row_as_event
from apps.integrations.services.hik_client import HikCentralClient, HikClientError
from apps.integrations.services.lxp_graphql_client import LXPAuthError, LXPGraphQLClient, LXPRequestError
from apps.integrations.services.telegram_notify import send_admin_alert

logger = logging.getLogger(__name__)


def _alert_lxp_failure(bucket: str, message: str, exc: BaseException | None = None) -> None:
    suffix = f": {exc}" if exc else ""
    body = f"[LXP][{bucket}] {message}{suffix}"
    ok, detail = send_admin_alert(body)
    if not ok:
        logger.warning("LXP alert not delivered (%s): %s", detail, body[:200])


@shared_task
def refresh_lxp_token() -> str:
    try:
        refresh_lxp_token_sync()
        return "token_refreshed"
    except LXPAuthError as e:
        logger.exception("LXP token refresh failed (auth)")
        _alert_lxp_failure("TOKEN", "refresh failed", e)
        raise
    except requests.Timeout as e:
        logger.exception("LXP token refresh failed (timeout)")
        _alert_lxp_failure("TIMEOUT", "refresh timeout", e)
        raise
    except Exception as e:
        logger.exception("LXP token refresh failed")
        _alert_lxp_failure("TOKEN", "refresh unexpected error", e)
        raise


@shared_task
def fetch_lxp_snapshot() -> str:
    yesterday = timezone.now().date() - timedelta(days=1)
    try:
        refresh_lxp_token_sync()
        client = LXPGraphQLClient()
        client.get_token()
        data = client.fetch_all_data(date=yesterday)
        LXPSnapshot.objects.update_or_create(date=yesterday, defaults={"data": data})

        from apps.progress.tasks import recalculate_rating_for_date

        recalculate_rating_for_date.delay(yesterday.isoformat())
        logger.info("LXP snapshot saved for %s", yesterday)
        return f"Snapshot for {yesterday} saved"
    except LXPAuthError as e:
        logger.exception("LXP snapshot fetch failed (auth)")
        _alert_lxp_failure("TOKEN", f"snapshot fetch failed for {yesterday}", e)
        raise
    except LXPRequestError as e:
        logger.exception("LXP snapshot fetch failed (graphql)")
        _alert_lxp_failure("GRAPHQL", f"snapshot fetch failed for {yesterday}", e)
        raise
    except requests.Timeout as e:
        logger.exception("LXP snapshot fetch failed (timeout)")
        _alert_lxp_failure("TIMEOUT", f"snapshot fetch failed for {yesterday}", e)
        raise
    except Exception as e:
        logger.exception("LXP snapshot fetch failed")
        _alert_lxp_failure("SNAPSHOT", f"snapshot fetch failed for {yesterday}", e)
        raise


@shared_task
def fetch_hik_events() -> str:
    """
    Забирает события доступа из HikCentral → HikEvent, затем выпускает ExternalEvent
    для пользователей с привязанной картой (hik_card_code).
    """
    if not getattr(settings, "HIK_FETCH_ENABLED", False):
        return "hik_disabled"
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
        return f"hik_fetch_error:{e}"
    inserted = 0
    seen = 0
    for row in rows:
        seen += 1
        _, created = save_hik_row_as_event(row)
        if created:
            inserted += 1
    proc_seen, ext_n, skipped = process_unprocessed_hik_events(limit=int(getattr(settings, "HIK_PROCESS_BATCH", 8000)))
    logger.info(
        "fetch_hik_events rows=%s new_db=%s process_seen=%s external_new=%s no_user_skip=%s",
        seen,
        inserted,
        proc_seen,
        ext_n,
        skipped,
    )
    return f"hik_saved={inserted}/{seen} external={ext_n} skipped_users={skipped}"


@shared_task
def process_hik_events_daily() -> str:
    """Доработка очереди необработанных событий (больший лимит)."""
    if not getattr(settings, "HIK_FETCH_ENABLED", False):
        return "hik_disabled"
    proc_seen, ext_n, skipped = process_unprocessed_hik_events(limit=50_000)
    return f"hik_daily processed={proc_seen} external={ext_n} skipped_users={skipped}"


@shared_task
def process_late_events() -> str:
    """Обработка HikEvent: опоздания, ExternalEvent, штрафы рейтинга."""
    if not getattr(settings, "HIK_FETCH_ENABLED", False):
        return "hik_disabled"
    proc_seen, ext_n, skipped = process_unprocessed_hik_events(
        limit=int(getattr(settings, "HIK_PROCESS_BATCH", 8000))
    )
    return f"hik_late processed={proc_seen} external={ext_n} skipped_users={skipped}"
