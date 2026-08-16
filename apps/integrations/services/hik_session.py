"""Сессия портала Hik Connect: браузер логинится один раз, дальше — обычный HTTP.

Зачем так: у портала нет OpenAPI, но его SPA ходит в собственный HTTP API
(`hik_web_client.py`). Единственное, что нельзя получить без браузера, —
сессионные cookies. Поэтому Playwright используется как «добыватель ключа»,
а не как способ кликать по меню каждый час.

Cookies кладутся в Redis и переиспользуются: раньше браузер поднимался
на каждый прогон (24 раза в сутки), логинился заново и оставлял процессы
Chromium висеть при любой ошибке.

Важно: портал, судя по всему, допускает одну активную сессию на аккаунт —
вход бота выкидывает сотрудника из веб-интерфейса и наоборот. Поэтому
логин защищён блокировкой (чтобы параллельные задачи не поднимали несколько
браузеров), а обновление сессии делается только по необходимости.
Для эксплуатации стоит завести отдельный сервисный аккаунт.
"""

from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit

from django.conf import settings
from django.core.cache import cache

from apps.integrations.services.browser_runtime import context_kwargs, launch_kwargs
from apps.integrations.services.hik_browser_export import HikBrowserExportError, _login
from apps.integrations.services.hik_browser_settings import hik_browser_config_from_settings

logger = logging.getLogger(__name__)

SESSION_CACHE_KEY = "hik:web:session"
SESSION_LOCK_KEY = "hik:web:session:lock"
SESSION_LOCK_TTL = 300  # логин с медленным порталом занимает до пары минут


class HikSessionError(RuntimeError):
    """Не удалось получить сессию портала."""


def _api_host() -> str:
    base = getattr(settings, "HIK_WEB_API_BASE", "") or ""
    return urlsplit(base).hostname or ""


def _relevant_cookie(cookie: dict, hosts: set[str]) -> bool:
    domain = (cookie.get("domain") or "").lstrip(".").lower()
    if not domain:
        return False
    return any(host == domain or host.endswith(f".{domain}") for host in hosts if host)


def _collect_cookies(context, hosts: set[str]) -> dict[str, str]:
    cookies = {}
    for cookie in context.cookies():
        if not _relevant_cookie(cookie, hosts):
            continue
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value:
            cookies[name] = value
    return cookies


def login_and_collect_cookies() -> dict[str, str]:
    """Поднять браузер, войти на портал и забрать cookies.

    Cookies нужны для домена API (`team.hikcentralconnectru.com`), а он
    отличается от домена входа, поэтому после логина мы даём SPA сходить
    в API — только тогда его cookies появляются в контексте.
    """
    from playwright.sync_api import sync_playwright

    config = hik_browser_config_from_settings()
    if not config.email or not config.password:
        raise HikSessionError("Не заданы HIK_WEB_EMAIL / HIK_WEB_PASSWORD")

    login_host = urlsplit(config.login_url).hostname or ""
    hosts = {h for h in (login_host, _api_host()) if h}

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs(headless=config.headless))
        try:
            context = browser.new_context(**context_kwargs())
            page = context.new_page()
            page.set_default_timeout(config.timeout_ms)

            try:
                _login(page, config)
            except HikBrowserExportError as exc:
                raise HikSessionError(str(exc)) from exc

            # Дать SPA обратиться к API, чтобы появились его cookies.
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception:
                pass
            page.wait_for_timeout(3_000)

            cookies = _collect_cookies(context, hosts)
        finally:
            # Без finally процессы Chromium оставались висеть при любой ошибке.
            browser.close()

    if not cookies:
        raise HikSessionError(
            "После входа не найдено ни одной cookie для доменов "
            f"{sorted(hosts)} — портал мог не завершить авторизацию"
        )
    logger.info("hik_session: получено cookies: %s", len(cookies))
    return cookies


def get_session_cookies(*, force_refresh: bool = False) -> dict[str, str]:
    """Вернуть cookies портала, при необходимости выполнив вход.

    Блокировка не даёт параллельным Celery-задачам поднять несколько браузеров
    и несколько раз залогиниться в один аккаунт.
    """
    if not force_refresh:
        cached = cache.get(SESSION_CACHE_KEY)
        if cached:
            return cached

    ttl = int(getattr(settings, "HIK_WEB_SESSION_TTL", 6 * 60 * 60))

    if not cache.add(SESSION_LOCK_KEY, "1", SESSION_LOCK_TTL):
        # Логин уже идёт в другом процессе — подождём его результат.
        deadline = time.time() + SESSION_LOCK_TTL
        while time.time() < deadline:
            time.sleep(2)
            cached = cache.get(SESSION_CACHE_KEY)
            if cached:
                return cached
            if not cache.get(SESSION_LOCK_KEY):
                break
        raise HikSessionError("Другой процесс не смог получить сессию портала")

    try:
        cookies = login_and_collect_cookies()
        cache.set(SESSION_CACHE_KEY, cookies, ttl)
        return cookies
    finally:
        cache.delete(SESSION_LOCK_KEY)


def drop_session() -> None:
    """Забыть сохранённую сессию (после 401 от API)."""
    cache.delete(SESSION_CACHE_KEY)
