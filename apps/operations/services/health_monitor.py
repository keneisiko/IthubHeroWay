"""Периодический мониторинг здоровья сервисов с алертами."""

from __future__ import annotations

from django.core.cache import cache

from apps.integrations.services.lxp_graphql_client import LXPGraphQLClient
from apps.integrations.services.telegram_alert import send_alert_to_admin
from apps.operations.health_views import _celery_ok, _db_ok, _redis_ok


def collect_health_issues() -> list[str]:
    issues: list[str] = []
    if not _db_ok():
        issues.append("PostgreSQL недоступна")
    if not _redis_ok():
        issues.append("Redis недоступен")
    if not _celery_ok():
        issues.append("Celery worker не отвечает на ping")

    token = cache.get(LXPGraphQLClient.TOKEN_CACHE_KEY)
    client = LXPGraphQLClient()
    if not token and not client.static_token:
        issues.append("LXP токен отсутствует в кеше (возможно, не обновлён)")

    return issues


def monitor_health_and_alert_sync() -> dict:
    issues = collect_health_issues()
    alerted = 0
    for issue in issues:
        key = issue.split()[0].lower()[:32]
        if send_alert_to_admin(
            title="Health-check: обнаружена проблема",
            message=issue,
            error_type="warning",
            deduplicate_key=f"health:{key}",
            is_critical=False,
        ):
            alerted += 1
    return {"issues": issues, "alerts_sent": alerted}
