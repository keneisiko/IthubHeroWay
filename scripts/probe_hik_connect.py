"""Probe Hik Connect RU portal (run in docker: manage.py shell or python scripts/probe_hik_connect.py)."""
from __future__ import annotations

import os
import sys
import time

from playwright.sync_api import sync_playwright

from apps.integrations.services.lxp_browser_token import _click_first, _force_fill_auth_inputs


def main() -> int:
    email = os.environ.get("HIK_WEB_EMAIL", "")
    password = os.environ.get("HIK_WEB_PASSWORD", "")
    login_url = os.environ.get(
        "HIK_WEB_LOGIN_URL",
        "https://www.hik-connectru.com/views/login/index.html#/login",
    )
    if not email or not password:
        print("Set HIK_WEB_EMAIL and HIK_WEB_PASSWORD", file=sys.stderr)
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(login_url, wait_until="domcontentloaded", timeout=60_000)
        time.sleep(5)
        print("URL1", page.url, "|", page.title())
        forced = _force_fill_auth_inputs(page, email, password)
        print("forced", forced)
        _click_first(
            page,
            [
                "button[type='submit']",
                "button:has-text('Войти')",
                "button:has-text('Login')",
                "button.el-button--primary",
                "button",
            ],
        )
        time.sleep(12)
        print("URL2", page.url, "|", page.title())
        texts = page.evaluate(
            """
            () => {
              const s = new Set();
              for (const el of document.querySelectorAll('*')) {
                const t = (el.innerText || '').trim();
                if (t && t.length < 60 && !t.includes('\\n') && /[А-Яа-яA-Za-z]/.test(t)) s.add(t);
              }
              return Array.from(s).slice(0, 80);
            }
            """
        )
        for t in texts:
            print(" -", t)
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
