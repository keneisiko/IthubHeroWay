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

    lxp_issue = _lxp_token_issue()
    if lxp_issue:
        issues.append(lxp_issue)

    return issues


def _lxp_token_issue() -> str:
    """Может ли платформа получить токен LXP — а не «лежит ли он в кеше».

    Раньше пустой кеш считался сбоем. Но он пуст каждую ночь: токен живёт
    в кеше 23 часа, а обновляется раз в сутки в 01:45, и с 00:45 до 01:45
    монитор слал «токен отсутствует», хотя любая задача при пустом кеше сама
    входит в LXP и берёт новый. После перезапуска Redis тревога шла весь
    день. Теперь при пустом кеше монитор сам получает токен — тревога только
    если LXP действительно не пускает.
    """
    if cache.get(LXPGraphQLClient.TOKEN_CACHE_KEY):
        return ""
    client = LXPGraphQLClient()
    if client.static_token:
        return ""
    try:
        client.get_token()
    except Exception as exc:  # noqa: BLE001 — любая причина отказа и есть проблема
        return f"LXP не выдаёт токен: {type(exc).__name__}: {str(exc)[:200]}"
    return ""


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
