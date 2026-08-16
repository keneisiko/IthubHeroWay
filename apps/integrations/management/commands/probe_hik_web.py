"""Разведка внутреннего API портала hik-connectru.

Зачем: OpenAPI-ключей у нас нет, а кликать по меню Playwright'ом каждый час —
хрупко. Но сам портал — обычное SPA, которое ходит в свой HTTP API. Эта команда
логинится браузером один раз, записывает все XHR-запросы и показывает, какие
именно эндпоинты отдают записи прохода. По результату заполняются переменные
HIK_WEB_API_* в .env, после чего данные можно тянуть обычным requests-клиентом
без зависимости от вёрстки.

Запускать вручную, разово (и повторно — если портал обновится):

    python manage.py probe_hik_web
    python manage.py probe_hik_web --headed --keep-open 60

Секреты в отчёте маскируются: значения заголовков авторизации, cookies, токенов
и пароля заменяются на «***». Отчёт можно безопасно приложить к задаче.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.integrations.services.browser_runtime import context_kwargs, launch_kwargs
from apps.integrations.services.hik_browser_settings import hik_browser_config_from_settings

# Заголовки и поля, значения которых нельзя писать в отчёт.
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-auth-token",
    "sessionid",
    "session-id",
    "token",
    "access-token",
    "x-csrf-token",
    "x-token",
    "userid",
    "x-user-id",
}
SENSITIVE_BODY_KEYS = re.compile(
    r"(password|passwd|token|secret|session|cookie|authorization)", re.IGNORECASE
)

# Запросы, которые почти наверняка относятся к записям прохода.
RECORD_HINTS = (
    "acs",
    "access",
    "door",
    "event",
    "record",
    "attendance",
    "person",
    "swipe",
    "turnstile",
)

STATIC_SUFFIXES = (
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".ico",
    ".map",
    ".gif",
)


def _mask_headers(headers: dict[str, str]) -> dict[str, str]:
    masked = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            masked[key] = f"*** ({len(value)} символов)"
        else:
            masked[key] = value
    return masked


def _mask_body(raw: str | None, password: str) -> str:
    if not raw:
        return ""
    text = raw[:2000]
    if password and password in text:
        text = text.replace(password, "***")
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return text

    def scrub(node: Any) -> Any:
        if isinstance(node, dict):
            return {
                k: ("***" if SENSITIVE_BODY_KEYS.search(str(k)) else scrub(v))
                for k, v in node.items()
            }
        if isinstance(node, list):
            return [scrub(item) for item in node[:5]]
        return node

    return json.dumps(scrub(parsed), ensure_ascii=False, indent=2)[:2000]


def _response_shape(node: Any, depth: int = 0) -> Any:
    """Свести JSON к описанию структуры без реальных значений."""
    if depth > 4:
        return "..."
    if isinstance(node, dict):
        return {k: _response_shape(v, depth + 1) for k, v in list(node.items())[:25]}
    if isinstance(node, list):
        if not node:
            return []
        return [_response_shape(node[0], depth + 1), f"... всего элементов: {len(node)}"]
    if isinstance(node, str):
        return f"str({len(node)})"
    return type(node).__name__


def _is_interesting(url: str) -> bool:
    lowered = url.lower().split("?")[0]
    if lowered.endswith(STATIC_SUFFIXES):
        return False
    return True


def _looks_like_records(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in RECORD_HINTS)


class Command(BaseCommand):
    help = "Записать сетевые запросы портала Hik Connect и предложить конфигурацию HIK_WEB_API_*"

    def add_arguments(self, parser):
        parser.add_argument(
            "--headed",
            action="store_true",
            help="Показать окно браузера (удобно, чтобы пройти по разделам руками)",
        )
        parser.add_argument(
            "--keep-open",
            type=int,
            default=0,
            help="Держать браузер открытым N секунд после навигации — успеть покликать вручную",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="",
            help="Куда записать отчёт (по умолчанию — в каталог выгрузок Hik)",
        )

    def handle(self, *args, **options):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise CommandError("Playwright не установлен: pip install playwright") from exc

        config = hik_browser_config_from_settings(debug=True)
        if not config.email or not config.password:
            raise CommandError(
                "Не заданы HIK_WEB_EMAIL / HIK_WEB_PASSWORD — без них зайти на портал нельзя"
            )

        headless = not options["headed"]
        keep_open = max(0, int(options["keep_open"]))
        requests_log: list[dict] = []

        self.stdout.write(f"Открываю {config.login_url} (headless={headless})…")

        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs(headless=headless))
            try:
                context = browser.new_context(**context_kwargs())
                page = context.new_page()
                page.set_default_timeout(config.timeout_ms)

                def on_response(response):
                    url = response.url
                    if not _is_interesting(url):
                        return
                    request = response.request
                    if request.resource_type not in {"xhr", "fetch", "document"}:
                        return
                    entry = {
                        "method": request.method,
                        "url": url,
                        "status": response.status,
                        "resource_type": request.resource_type,
                        "request_headers": _mask_headers(request.headers),
                        "request_body": _mask_body(request.post_data, config.password),
                        "response_shape": None,
                        "looks_like_records": _looks_like_records(url),
                    }
                    content_type = (response.headers or {}).get("content-type", "")
                    if "json" in content_type.lower():
                        try:
                            entry["response_shape"] = _response_shape(response.json())
                        except Exception:
                            entry["response_shape"] = "не удалось разобрать JSON"
                    requests_log.append(entry)

                page.on("response", on_response)

                page.goto(config.login_url, wait_until="domcontentloaded")
                self._login(page, config)

                if config.records_url:
                    self.stdout.write(f"Перехожу на {config.records_url}…")
                    page.goto(config.records_url, wait_until="domcontentloaded")
                    page.wait_for_timeout(5_000)
                elif config.nav_steps:
                    from apps.integrations.services.hik_browser_export import _click_nav_step

                    for step in config.nav_steps:
                        self.stdout.write(f"Кликаю по «{step}»…")
                        if not _click_nav_step(page, step):
                            self.stdout.write(
                                self.style.WARNING(f"  пункт «{step}» не найден — продолжаю")
                            )
                        page.wait_for_timeout(3_000)

                if keep_open:
                    self.stdout.write(
                        self.style.NOTICE(
                            f"Браузер открыт {keep_open} с — откройте раздел записей прохода "
                            "и нажмите «Поиск», чтобы поймать нужный запрос"
                        )
                    )
                    page.wait_for_timeout(keep_open * 1_000)

                storage_keys = self._storage_keys(page)
            finally:
                browser.close()

        report_path = self._write_report(requests_log, storage_keys, options["output"])
        self._print_summary(requests_log, storage_keys, report_path)

    def _login(self, page, config) -> None:
        from apps.integrations.services.hik_browser_export import _login

        _login(page, config)

    def _storage_keys(self, page) -> dict:
        """Имена ключей localStorage/sessionStorage — где искать токен сессии."""
        try:
            return page.evaluate(
                """() => ({
                    localStorage: Object.keys(window.localStorage || {}),
                    sessionStorage: Object.keys(window.sessionStorage || {}),
                    url: window.location.href,
                })"""
            )
        except Exception:
            return {}

    def _write_report(self, requests_log: list[dict], storage_keys: dict, output: str) -> Path:
        if output:
            path = Path(output)
        else:
            from django.conf import settings

            base = Path(getattr(settings, "HIK_BROWSER_DOWNLOAD_DIR", "/tmp/hik_exports"))
            base.mkdir(parents=True, exist_ok=True)
            path = base / f"hik_probe_{datetime.now():%Y%m%d_%H%M%S}.json"

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "captured_at": datetime.now().isoformat(),
                    "storage_keys": storage_keys,
                    "requests": requests_log,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    def _print_summary(self, requests_log: list[dict], storage_keys: dict, report_path: Path) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Отчёт: {report_path}"))
        self.stdout.write(f"Всего перехвачено запросов: {len(requests_log)}")

        candidates = [r for r in requests_log if r["looks_like_records"] and r["status"] < 400]
        if not candidates:
            self.stdout.write(
                self.style.WARNING(
                    "Запросы, похожие на записи прохода, не найдены. "
                    "Запустите с --headed --keep-open 120, откройте раздел вручную и нажмите «Поиск»."
                )
            )
            return

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Кандидаты на эндпоинт записей прохода:"))
        for entry in candidates[:10]:
            self.stdout.write(f"  {entry['method']:6} {entry['status']}  {entry['url'][:140]}")

        best = candidates[0]
        from urllib.parse import urlsplit

        parts = urlsplit(best["url"])
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Предлагаемая конфигурация для .env:"))
        self.stdout.write(f"  HIK_WEB_API_BASE={parts.scheme}://{parts.netloc}")
        self.stdout.write(f"  HIK_WEB_API_RECORDS_PATH={parts.path}")
        self.stdout.write(f"  HIK_WEB_API_RECORDS_METHOD={best['method']}")

        auth_headers = [
            name
            for name in best["request_headers"]
            if name.lower() in SENSITIVE_HEADERS and name.lower() != "cookie"
        ]
        if auth_headers:
            self.stdout.write(f"  HIK_WEB_API_AUTH_HEADERS={','.join(auth_headers)}")
        else:
            self.stdout.write("  HIK_WEB_API_AUTH_HEADERS=  # авторизация только через cookie")

        if storage_keys:
            self.stdout.write("")
            self.stdout.write(
                f"Ключи хранилищ (там может лежать токен): "
                f"{storage_keys.get('localStorage', [])[:15]}"
            )
