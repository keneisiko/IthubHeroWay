"""Общая логика задач Celery для LXP (без циклических импортов с signals)."""

from __future__ import annotations

import logging

from apps.integrations.services.lxp_graphql_client import LXPGraphQLClient

logger = logging.getLogger(__name__)


def refresh_lxp_token_sync() -> str:
    """Обновляет токен в Redis и возвращает его строковое представление (длина для логов)."""
    token = LXPGraphQLClient().login()
    logger.info("LXP token refreshed (%s chars)", len(token))
    return token
