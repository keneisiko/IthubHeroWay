"""Build Hik browser export config from Django settings."""

from __future__ import annotations

from django.conf import settings

from apps.integrations.services.hik_browser_export import HikBrowserExportConfig


def hik_browser_config_from_settings(*, debug: bool = False) -> HikBrowserExportConfig:
    nav_raw = getattr(settings, "HIK_WEB_NAV_STEPS", "") or ""
    nav_steps = tuple(s.strip() for s in nav_raw.split("|") if s.strip())
    return HikBrowserExportConfig(
        login_url=getattr(
            settings,
            "HIK_WEB_LOGIN_URL",
            "https://www.hik-connectru.com/views/login/index.html#/login",
        ),
        email=getattr(settings, "HIK_WEB_EMAIL", "") or "",
        password=getattr(settings, "HIK_WEB_PASSWORD", "") or "",
        nav_steps=nav_steps,
        records_url=getattr(settings, "HIK_WEB_RECORDS_URL", "") or "",
        headless=bool(getattr(settings, "HIK_BROWSER_HEADLESS", True)),
        timeout_ms=int(getattr(settings, "HIK_BROWSER_TIMEOUT_MS", 120_000)),
        debug=debug,
        download_dir=getattr(settings, "HIK_BROWSER_DOWNLOAD_DIR", "/tmp/hik_exports"),
    )


def browser_export_enabled() -> bool:
    mode = getattr(settings, "HIK_DATA_MODE", "snapshot")
    if mode == "off":
        return False
    if mode == "browser":
        return True
    return bool(getattr(settings, "HIK_USE_BROWSER_EXPORT", False))
