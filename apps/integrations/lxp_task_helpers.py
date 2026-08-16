"""Общая логика задач Celery для LXP (без циклических импортов с signals)."""

from __future__ import annotations

import logging

from apps.integrations.services.lxp_graphql_client import LXPGraphQLClient

logger = logging.getLogger(__name__)


def refresh_lxp_token_sync(*, force: bool = False) -> str:
    """Убедиться, что в кеше есть рабочий токен LXP.

    Раньше здесь безусловно вызывался `login()`, из-за чего:

    * задачи логинились повторно поверх свежего токена — beat обновляет токен
      в 01:45, а снимок в 02:00 делал это ещё раз, плюс третий раз внутри
      `get_token()`;
    * при заданном `LXP_API_TOKEN` (статический токен, вход не нужен) задача
      всё равно шла логиниться и падала, если не заполнены логин и пароль бота.

    `get_token()` учитывает и статический токен, и кеш, и блокировку входа.
    """
    token = LXPGraphQLClient().get_token(force_refresh=force)
    logger.info("LXP token ready (%s chars, force=%s)", len(token), force)
    return token
