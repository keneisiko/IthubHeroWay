from __future__ import annotations

import re
import time
from dataclasses import dataclass

from playwright.sync_api import sync_playwright

from apps.integrations.services.browser_runtime import context_kwargs, launch_kwargs


class BrowserTokenFetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrowserTokenConfig:
    web_base_url: str
    login_url: str
    graphql_host: str
    email: str
    password: str
    headless: bool = True
    timeout_ms: int = 60_000
    debug: bool = False


TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+$")


def _fill_first(page, selectors: list[str], value: str) -> bool:
    targets = [page, *page.frames]
    for target in targets:
        for selector in selectors:
            try:
                target.wait_for_selector(selector, timeout=4_000, state="visible")
            except Exception:
                continue
            locator = target.locator(selector).first
            try:
                if not locator.is_editable():
                    continue
                locator.click()
                locator.fill("")
                locator.type(value, delay=20)
                current_value = (locator.input_value() or "").strip()
                if current_value == value.strip():
                    return True
                target.evaluate(
                    """
                    ([sel, val]) => {
                      const el = document.querySelector(sel);
                      if (!el) return;
                      const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
                      if (descriptor && descriptor.set) descriptor.set.call(el, val);
                      else el.value = val;
                      el.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
                      el.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                      el.dispatchEvent(new Event('blur', { bubbles: true, composed: true }));
                    }
                    """,
                    [selector, value],
                )
                fixed_value = (locator.input_value() or "").strip()
                if fixed_value == value.strip():
                    return True
            except Exception:
                continue
    return False


def _click_first(page, selectors: list[str]) -> bool:
    targets = [page, *page.frames]
    for target in targets:
        for selector in selectors:
            try:
                target.wait_for_selector(selector, timeout=4_000, state="visible")
            except Exception:
                continue
            locator = target.locator(selector).first
            try:
                locator.click()
                return True
            except Exception:
                continue
    return False


def _extract_bearer(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip()
    if value.lower().startswith("bearer "):
        value = value.split(" ", 1)[1].strip()
    if TOKEN_PATTERN.match(value):
        return value
    return None


def _token_from_web_storage(page) -> str | None:
    script = """
    () => {
      const out = [];
      for (const storage of [window.localStorage, window.sessionStorage]) {
        for (let i = 0; i < storage.length; i++) {
          const key = storage.key(i);
          const value = storage.getItem(key);
          out.push([key || "", value || ""]);
        }
      }
      return out;
    }
    """
    pairs = page.evaluate(script) or []
    for key, value in pairs:
        token = _extract_bearer(value)
        if token:
            return token
        if any(mark in (key or "").lower() for mark in ("token", "jwt", "access")):
            token = _extract_bearer(value)
            if token:
                return token
    return None


def _token_from_cookies(context) -> str | None:
    for cookie in context.cookies():
        token = _extract_bearer(cookie.get("value"))
        if token:
            return token
        name = (cookie.get("name") or "").lower()
        if any(mark in name for mark in ("token", "jwt", "access")):
            token = _extract_bearer(cookie.get("value"))
            if token:
                return token
    return None


def _force_fill_auth_inputs(page, email: str, password: str, *, submit: bool = True) -> dict:
    """Заполнить поля логина через JS и (опционально) отправить форму.

    `submit=False` нужен вызывающему коду, который сам решает, как и когда
    отправлять форму: иначе получается несколько попыток входа подряд
    (requestSubmit здесь + клик по кнопке + Enter снаружи), что для портала
    неотличимо от перебора пароля.

    В ответе поле `submitted` сообщает, была ли форма отправлена отсюда.
    """
    totals = {"email_len": 0, "password_len": 0, "has_form": False, "submitted": False}
    targets = [page, *page.frames]
    for target in targets:
        try:
            result = target.evaluate(
        """
        ([emailValue, passwordValue, shouldSubmit]) => {
          const visible = (el) => {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
          };

          const pickFirst = (selectors) => {
            for (const sel of selectors) {
              const nodes = Array.from(document.querySelectorAll(sel)).filter(visible);
              if (nodes.length) return nodes[0];
            }
            return null;
          };

          const setValue = (el, val) => {
            if (!el) return false;
            const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            const desc = Object.getOwnPropertyDescriptor(proto, 'value');
            if (desc && desc.set) desc.set.call(el, val);
            else el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
            el.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true, composed: true }));
            return true;
          };

          const emailInput = pickFirst([
            "input[type='email']",
            "input[name='email']",
            "input[name='login']",
            "input[name='username']",
            "input[name*='mail']",
            "input[autocomplete='username']",
            "input[type='text']",
            "input:not([type='hidden']):not([type='password'])",
            "input[placeholder*='mail' i]",
            "input[placeholder*='почт' i]",
          ]);
          const passwordInput = pickFirst([
            "input[type='password']",
            "input[name='password']",
            "input[name*='pass']",
            "input[autocomplete='current-password']",
            "input[placeholder*='парол' i]",
            "input[placeholder*='password' i]",
          ]);

          setValue(emailInput, emailValue);
          setValue(passwordInput, passwordValue);

          const result = {
            email_len: (emailInput?.value || '').length,
            password_len: (passwordInput?.value || '').length,
            has_form: Boolean((emailInput && emailInput.form) || (passwordInput && passwordInput.form)),
          };

          const form = (emailInput && emailInput.form) || (passwordInput && passwordInput.form);
          if (form && shouldSubmit && result.password_len > 0) {
            if (typeof form.requestSubmit === 'function') form.requestSubmit();
            else form.submit();
            result.submitted = true;
          }
          return result;
        }
        """,
                [email, password, submit],
            )
        except Exception:
            continue
        totals["email_len"] = max(int(result.get("email_len") or 0), totals["email_len"])
        totals["password_len"] = max(int(result.get("password_len") or 0), totals["password_len"])
        totals["has_form"] = totals["has_form"] or bool(result.get("has_form"))
        totals["submitted"] = totals["submitted"] or bool(result.get("submitted"))
    return totals


def _extract_token_from_json(data) -> str | None:
    if isinstance(data, dict):
        for key, value in data.items():
            key_l = str(key).lower()
            if any(mark in key_l for mark in ("token", "access_token", "access", "jwt")):
                token = _extract_bearer(value if isinstance(value, str) else None)
                if token:
                    return token
            nested = _extract_token_from_json(value)
            if nested:
                return nested
    elif isinstance(data, list):
        for item in data:
            nested = _extract_token_from_json(item)
            if nested:
                return nested
    elif isinstance(data, str):
        return _extract_bearer(data)
    return None


def fetch_lxp_bearer_token(config: BrowserTokenConfig) -> str:
    token_box: dict[str, str] = {}
    graphql_hits: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs(headless=config.headless))
        context = browser.new_context(**context_kwargs())
        page = context.new_page()

        def on_request(request):
            if (
                config.graphql_host not in request.url
                and "/graphql" not in request.url.lower()
                and "graphql" not in request.url.lower()
            ):
                return
            graphql_hits.append(request.url)
            auth = request.headers.get("authorization") or request.headers.get("Authorization")
            token = _extract_bearer(auth)
            if token:
                token_box["token"] = token

        def on_response(response):
            url = response.url.lower()
            if config.graphql_host not in url and "graphql" not in url:
                return
            try:
                body = response.json()
            except Exception:
                return
            token = _extract_token_from_json(body)
            if token:
                token_box["token"] = token

        page.on("request", on_request)
        page.on("response", on_response)
        page.goto(config.login_url or config.web_base_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass

        email_ok = _fill_first(
            page,
            [
                "input[type='email']",
                "input[name='email']",
                "input[name*='email']",
                "input[placeholder*='mail']",
                "input[placeholder*='Email']",
                "input[placeholder*='Почт']",
                "input[autocomplete='username']",
            ],
            config.email,
        )
        password_ok = _fill_first(
            page,
            [
                "input[type='password']",
                "input[name='password']",
                "input[name*='password']",
                "input[placeholder*='парол']",
                "input[placeholder*='Password']",
                "input[autocomplete='current-password']",
            ],
            config.password,
        )
        if not email_ok:
            try:
                page.get_by_label("Email", exact=False).first.fill(config.email)
                email_ok = True
            except Exception:
                pass
        if not email_ok:
            try:
                page.get_by_label("Почта", exact=False).first.fill(config.email)
                email_ok = True
            except Exception:
                pass
        if not password_ok:
            try:
                page.get_by_label("Password", exact=False).first.fill(config.password)
                password_ok = True
            except Exception:
                pass
        if not password_ok:
            try:
                page.get_by_label("Пароль", exact=False).first.fill(config.password)
                password_ok = True
            except Exception:
                pass

        # Проверяем поля до отправки: раньше форма с логином и паролем уже
        # уходила на сервер, и только потом код падал с «поля не найдены».
        if not email_ok or not password_ok:
            browser.close()
            raise BrowserTokenFetchError("Login form fields not found on page.")

        forced = _force_fill_auth_inputs(page, config.email, config.password, submit=False)

        clicked = _click_first(
            page,
            [
                "button[type='submit']",
                "button:has-text('Войти')",
                "button:has-text('Вход')",
                "button:has-text('Login')",
            ],
        )
        # Форма отправляется ровно один раз: либо кликом по кнопке, либо Enter.
        # Раньше Enter нажимался именно тогда, когда кнопка уже была нажата,
        # то есть логин уходил дважды.
        if not clicked and not forced.get("submitted"):
            page.keyboard.press("Enter")
        try:
            page.wait_for_load_state("networkidle", timeout=min(config.timeout_ms, 15_000))
        except Exception:
            pass

        # Wait up to timeout for GraphQL bearer, with fallbacks from web storage and cookies.
        deadline = time.time() + (config.timeout_ms / 1000.0)
        while time.time() < deadline:
            if token_box.get("token"):
                token = token_box["token"]
                browser.close()
                return token
            storage_token = _token_from_web_storage(page)
            if storage_token:
                browser.close()
                return storage_token
            cookie_token = _token_from_cookies(context)
            if cookie_token:
                browser.close()
                return cookie_token
            page.wait_for_timeout(500)

        if config.debug:
            current_url = page.url
            page_title = page.title()
            storage_dump = page.evaluate(
                """
                () => {
                  const out = { localStorage: [], sessionStorage: [] };
                  for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    out.localStorage.push(key || "");
                  }
                  for (let i = 0; i < sessionStorage.length; i++) {
                    const key = sessionStorage.key(i);
                    out.sessionStorage.push(key || "");
                  }
                  return out;
                }
                """
            )
            browser.close()
            raise BrowserTokenFetchError(
                "Could not intercept token. "
                f"page_url={current_url}, page_title={page_title!r}, "
                f"forced_email_len={forced.get('email_len')}, forced_password_len={forced.get('password_len')}, "
                f"submit_clicked={clicked}, has_form={forced.get('has_form')}, "
                f"frames={len(page.frames)}, "
                f"graphql_hits={len(graphql_hits)}, "
                f"sample_graphql_url={(graphql_hits[0] if graphql_hits else 'none')}, "
                f"local_storage_keys={storage_dump.get('localStorage', [])}, "
                f"session_storage_keys={storage_dump.get('sessionStorage', [])}"
            )

        browser.close()
        raise BrowserTokenFetchError("Could not intercept Bearer token from GraphQL requests.")

