"""Hik Connect web portal export via Playwright (XLSX download), similar to LXP browser bot."""

from __future__ import annotations

import logging
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from django.core.cache import cache
from playwright.sync_api import Page, sync_playwright

from apps.integrations.services.browser_runtime import (
    context_kwargs,
    dismiss_cookie_banner,
    launch_kwargs,
)
from apps.integrations.services.lxp_browser_token import (
    BrowserTokenFetchError,
    _click_first,
    _fill_first,
    _force_fill_auth_inputs,
)

logger = logging.getLogger(__name__)

# Блокировка на время браузерной выгрузки: портал допускает одну активную
# сессию на аккаунт, параллельные запуски выбивают друг друга.
EXPORT_LOCK_KEY = "hik:browser_export:lock"
EXPORT_LOCK_TTL = 900


class HikBrowserExportError(RuntimeError):
    pass


@dataclass(frozen=True)
class HikBrowserExportConfig:
    login_url: str
    email: str
    password: str
    nav_steps: tuple[str, ...] = ()
    records_url: str = ""
    headless: bool = True
    timeout_ms: int = 120_000
    debug: bool = False
    download_dir: str = "/tmp/hik_exports"


SEARCH_LABELS = ("Search", "Поиск", "Query", "Найти", "Применить", "OK", "确定")
EXPORT_LABELS = ("Export", "Экспорт", "Export to Excel", "Export Excel", "Export All")
EXCEL_LABELS = ("Excel", "XLSX", "xlsx", "Эксель", "Microsoft Excel")

NAV_ALIASES: dict[str, tuple[str, ...]] = {
    "контроль доступа": ("Access Control", "Access control"),
    "записи прохода": ("Search", "Identity Access", "Access Records", "Identity Access Search"),
    "access control": ("Контроль доступа",),
    "search": ("Поиск", "Записи прохода"),
}


def _click_by_text(page: Page, label: str) -> bool:
    targets = [page, *page.frames]
    for target in targets:
        for pattern in (label, label.lower(), label.upper()):
            try:
                locator = target.get_by_role("button", name=pattern, exact=False).first
                if locator.count() and locator.is_visible():
                    locator.click(timeout=4_000)
                    return True
            except Exception:
                pass
            try:
                locator = target.get_by_text(pattern, exact=False).first
                if locator.count() and locator.is_visible():
                    locator.click(timeout=4_000)
                    return True
            except Exception:
                continue
    return _click_first(
        page,
        [
            f"button:has-text('{label}')",
            f"a:has-text('{label}')",
            f"span:has-text('{label}')",
            f"text={label}",
        ],
    )


def _click_nav_step(page: Page, step: str) -> bool:
    if _click_by_text(page, step):
        return True
    aliases = NAV_ALIASES.get(step.strip().lower(), ())
    for alias in aliases:
        if _click_by_text(page, alias):
            return True
    return False


# Поля входа на hik-connectru не имеют name/id — только placeholder, а рядом
# на странице лежат input[type=text] от выпадающих списков Element-UI
# (страна, язык) и их поисковые строки.
#
# Привязка к <form> не работает: на странице ровно одна форма, и поля входа
# в неё не входят — внутри оказывается только поиск по списку регионов.
# Из-за префикса `form ` логин уезжал именно туда: в поле «Account/Email»
# оставалось пусто, а сверху в выборе региона появлялся адрес почты.
# Поэтому селекторы идут по плейсхолдеру и явно исключают readonly-поля
# и строки выбора («Please Select», «Select the ...»).
_NOT_A_SELECT = ":not([readonly]):not([placeholder*='Select' i])"

ACCOUNT_SELECTORS = (
    f"input[placeholder*='Account' i]{_NOT_A_SELECT}",
    f"input[placeholder*='Email' i]{_NOT_A_SELECT}",
    f"input[placeholder*='Аккаунт' i]{_NOT_A_SELECT}",
    f"input[placeholder*='Почт' i]{_NOT_A_SELECT}",
    f"input[type='text']{_NOT_A_SELECT}",
)
PASSWORD_SELECTORS = (
    "input[type='password']",
)
LOGIN_BUTTON_SELECTORS = (
    "button.login-form-button",
    "form button[type='submit']",
    "button:has-text('Login')",
    "button:has-text('Войти')",
    "button:has-text('Sign In')",
)


def _account_value(page: Page) -> str:
    """Что реально лежит в поле логина после заполнения."""
    for selector in ACCOUNT_SELECTORS:
        try:
            field = page.locator(selector).first
            if field.count() and field.is_visible():
                return (field.input_value() or "").strip()
        except Exception:
            continue
    return ""


def _login(page: Page, config: HikBrowserExportConfig) -> None:
    page.goto(config.login_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except Exception:
        pass

    # SPA дорисовывает форму уже после networkidle, и на медленном канале это
    # занимает десятки секунд. Ждём появления самого поля, а не фиксированный
    # таймер: иначе поля «то находятся, то нет» от запуска к запуску.
    form_deadline = max(30_000, min(config.timeout_ms, 120_000))
    try:
        page.wait_for_selector(ACCOUNT_SELECTORS[0], timeout=form_deadline)
    except Exception:
        logger.warning(
            "Hik login: поле логина не появилось за %s мс (url=%s)", form_deadline, page.url
        )

    dismiss_cookie_banner(page)

    filled_account = _fill_first(page, list(ACCOUNT_SELECTORS), config.email)
    filled_password = _fill_first(page, list(PASSWORD_SELECTORS), config.password)

    forced = {}
    if not (filled_account and filled_password):
        forced = _force_fill_auth_inputs(page, config.email, config.password, submit=False)

    account_ok = filled_account or forced.get("email_len", 0) > 0
    password_ok = filled_password or forced.get("password_len", 0) > 0

    # Читаем поле обратно: если логин ушёл не туда (а он уезжал в выбор
    # региона), портал ответит «неверные данные» через две минуты ожидания,
    # и по сообщению будет не понять, что дело в селекторе.
    if account_ok and _account_value(page) != config.email.strip():
        raise HikBrowserExportError(
            "Логин не попал в поле «Account/Email» на странице входа: "
            "вероятно, вёрстка портала изменилась. Проверьте скриншот "
            "(--debug) и селекторы ACCOUNT_SELECTORS."
        )

    if not account_ok or not password_ok:
        raise HikBrowserExportError(
            "Форма логина на портале Hik Connect не найдена. "
            "Частая причина — пустая страница в headless-режиме: портал отдаёт "
            "заглушку, если в user-agent есть HeadlessChrome."
        )

    # Форма отправляется ровно один раз. Раньше подряд шли requestSubmit
    # (внутри _force_fill_auth_inputs), клик по кнопке и Enter — три попытки
    # входа за один запуск, что для портала выглядит как перебор пароля.
    if not forced.get("submitted"):
        if not _click_first(page, list(LOGIN_BUTTON_SELECTORS)):
            page.keyboard.press("Enter")

    login_wait_s = max(30, min(config.timeout_ms // 1000, 120))
    if not _wait_for_login_result(page, timeout_s=login_wait_s):
        raise HikBrowserExportError(
            f"Вход на портал Hik Connect не выполнен: страница логина не сменилась за {login_wait_s} с. "
            "Проверьте HIK_WEB_EMAIL/HIK_WEB_PASSWORD, капчу или требование смены пароля "
            "(запустите probe_hik_web --headed, чтобы увидеть страницу)."
        )

    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass
    page.wait_for_timeout(2_000)


def _on_login_page(page: Page) -> bool:
    """Мы всё ещё на странице входа?

    Портал — SPA с хешевой маршрутизацией, и после успешного входа адрес
    выглядит так:

        до:    .../views/login/index.html#/login
        после: .../views/login/index.html#/portal

    Путь не меняется и всегда содержит «/login/», поэтому судить по нему нельзя:
    любая проверка пути считает вход неудавшимся навсегда. Признак — только хеш.
    """
    url = (page.url or "").lower()
    path, sep, fragment = url.partition("#")
    if sep:
        return fragment.startswith("/login") or fragment in {"", "/"}
    return path.rstrip("/").endswith("/login")


def _wait_for_login_result(page: Page, *, timeout_s: int = 30) -> bool:
    """Дождаться ухода со страницы логина.

    Возвращает False, если вход не удался: раньше истечение таймаута молча
    игнорировалось и выполнение шло дальше — до самой попытки экспорта, где
    ошибка выглядела как «не найдена кнопка Экспорт».
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not _on_login_page(page):
            return True
        page.wait_for_timeout(500)
    return not _on_login_page(page)


# Портал регулярно показывает поверх страницы модалку — «Request timeout»,
# просроченный сервис отчётов, предложение сменить пароль. Пока она открыта,
# клики по меню попадают в затемнение, а не в пункт: экспорт молча оставался
# на главной и падал по таймауту ожидания загрузки файла.
DIALOG_CLOSE_SELECTORS = (
    ".el-message-box__btns button",
    ".el-popover button",
    ".el-popover__title + div button",
    ".el-dialog__footer button",
    ".el-message-box__headerbtn",
    ".el-dialog__headerbtn",
    "button:has-text('Close')",
    "button:has-text('Закрыть')",
    "button:has-text('OK')",
)


def _dismiss_dialogs(page: Page, *, attempts: int = 3) -> int:
    """Закрыть модальные окна, если они перекрывают страницу."""
    closed = 0
    for _ in range(attempts):
        overlay = page.locator(
            ".el-message-box__wrapper, .el-dialog__wrapper, .v-modal, .el-popover:visible"
        ).first
        try:
            if not overlay.count() or not overlay.is_visible():
                break
        except Exception:
            break
        for selector in DIALOG_CLOSE_SELECTORS:
            try:
                button = page.locator(selector).first
                if button.count() and button.is_visible():
                    button.click(timeout=3_000)
                    closed += 1
                    page.wait_for_timeout(500)
                    break
            except Exception:
                continue
        else:
            # Кнопку не нашли — пробуем клавишу Escape.
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
            except Exception:
                break
    if closed:
        logger.info("Hik: закрыто модальных окон: %s", closed)
    return closed


def _navigate_to_records(page: Page, config: HikBrowserExportConfig) -> None:
    _dismiss_dialogs(page)

    if not config.records_url and not config.nav_steps:
        # Без маршрута скрипт оставался на главной портала и падал только
        # через таймаут ожидания загрузки — по сообщению было не понять, что
        # дело в пустой настройке.
        raise HikBrowserExportError(
            "Не задан маршрут к записям прохода: укажите HIK_WEB_RECORDS_URL "
            "или HIK_WEB_NAV_STEPS (например, «Access Control|Search»)."
        )

    if config.records_url:
        page.goto(config.records_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass
        page.wait_for_timeout(1_500)
        return

    for step in config.nav_steps:
        step = step.strip()
        if not step:
            continue
        if not _click_nav_step(page, step):
            logger.warning("Hik nav step not found: %s (url=%s)", step, page.url)
        page.wait_for_timeout(1_500)
        # Переход мог снова открыть модалку — закрываем перед следующим шагом.
        _dismiss_dialogs(page)


def _set_date_range(page: Page, start: date, end: date) -> None:
    start_s = start.isoformat()
    end_s = end.isoformat()
    ru_start = start.strftime("%d.%m.%Y")
    ru_end = end.strftime("%d.%m.%Y")

    date_inputs = page.locator("input[type='date']")
    if date_inputs.count() >= 2:
        date_inputs.nth(0).fill(start_s)
        date_inputs.nth(1).fill(end_s)
        return
    if date_inputs.count() == 1:
        date_inputs.first.fill(start_s)
        return

    editors = page.locator(".el-date-editor input, .el-range-input, input[placeholder*='date' i], input[placeholder*='дата' i]")
    count = editors.count()
    if count >= 2:
        try:
            editors.nth(0).click()
            editors.nth(0).fill(ru_start)
            editors.nth(1).click()
            editors.nth(1).fill(ru_end)
            page.keyboard.press("Escape")
            return
        except Exception:
            pass

    values = [ru_start, ru_end, start_s, end_s]
    for idx in range(min(count, 2)):
        try:
            editors.nth(idx).click()
            editors.nth(idx).fill(values[idx])
        except Exception:
            continue

    if count:
        page.keyboard.press("Escape")
        return

    _fill_first(page, ["input[placeholder*='Start' i]", "input[placeholder*='Нач' i]"], ru_start)
    _fill_first(page, ["input[placeholder*='End' i]", "input[placeholder*='Кон' i]"], ru_end)


def _click_search(page: Page) -> None:
    _dismiss_dialogs(page)
    for label in SEARCH_LABELS:
        if _click_by_text(page, label):
            page.wait_for_timeout(2_000)
            return
    _click_first(page, ["button.el-button--primary", "button[type='button']"])


def _click_export_menu(page: Page) -> bool:
    _dismiss_dialogs(page)
    for label in EXPORT_LABELS:
        if _click_by_text(page, label):
            return True
    return _click_first(
        page,
        [
            "button:has-text('Export')",
            "button:has-text('Экспорт')",
            ".export-btn",
            "[class*='export']",
        ],
    )


def _pick_excel_format(page: Page) -> None:
    page.wait_for_timeout(600)
    for label in EXCEL_LABELS:
        try:
            loc = page.get_by_text(label, exact=False).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=3_000)
                return
        except Exception:
            continue
    for selector in (
        "li:has-text('Excel')",
        "li:has-text('XLSX')",
        ".el-dropdown-menu__item:has-text('Excel')",
        ".el-dropdown-menu__item:has-text('Экспорт')",
    ):
        try:
            loc = page.locator(selector).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=2_000)
                return
        except Exception:
            continue


def _trigger_export(page: Page, timeout_ms: int, download_dir: Path) -> Path:
    with page.expect_download(timeout=timeout_ms) as download_info:
        if not _click_export_menu(page):
            raise HikBrowserExportError("Export button not found on Hik Connect page.")
        _pick_excel_format(page)

    download = download_info.value
    suffix = Path(download.suggested_filename or "hik_export.xlsx").suffix.lower()
    if not suffix:
        suffix = ".xlsx"
    # Метка времени с точностью до секунды приводила к коллизии, если два
    # запуска скачивали файл в одну секунду: второй затирал первый.
    out = download_dir / f"hik_{int(time.time())}_{uuid.uuid4().hex[:8]}{suffix}"
    download.save_as(str(out))
    return out


def cleanup_old_exports(download_dir: Path, *, keep_days: int = 7) -> int:
    """Удалить старые выгрузки.

    Скачанные файлы не удалялись никогда: при ежедневной выгрузке каталог
    рос бесконечно. Свежие оставляем — они нужны для разбора инцидентов.
    """
    if not download_dir.exists():
        return 0
    threshold = time.time() - keep_days * 24 * 3600
    removed = 0
    for path in download_dir.iterdir():
        if not path.is_file() or not path.name.startswith("hik_"):
            continue
        try:
            if path.stat().st_mtime < threshold:
                path.unlink()
                removed += 1
        except OSError:
            logger.debug("Не удалось удалить старую выгрузку %s", path)
    if removed:
        logger.info("Удалено старых выгрузок Hik: %s", removed)
    return removed


def _save_debug_artifacts(page: Page, download_dir: Path) -> tuple[Path, Path]:
    stamp = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
    screenshot = download_dir / f"hik_debug_{stamp}.png"
    html = download_dir / f"hik_debug_{stamp}.html"
    page.screenshot(path=str(screenshot), full_page=True)
    html.write_text(page.content(), encoding="utf-8")
    return screenshot, html


def _extract_xlsx_from_download(path: Path) -> Path:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.lower().endswith((".xlsx", ".xlsm", ".csv")):
                    out = path.with_suffix(Path(name).suffix)
                    out.write_bytes(zf.read(name))
                    return out
        raise HikBrowserExportError(f"ZIP export has no xlsx/csv inside: {path.name}")
    return path


def fetch_hik_xlsx_export(
    config: HikBrowserExportConfig,
    *,
    start_date: date,
    end_date: date | None = None,
) -> Path:
    """Login, navigate to access records, filter dates, download XLSX."""
    if not config.email or not config.password:
        raise HikBrowserExportError("HIK_WEB_EMAIL / HIK_WEB_PASSWORD are required.")

    end = end_date or start_date
    download_dir = Path(config.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    cleanup_old_exports(download_dir)

    # Портал допускает одну активную сессию на аккаунт, поэтому два браузера,
    # запущенных одновременно, выбивают друг друга. Раньше блокировки не было
    # вовсе, и ночная выгрузка могла наложиться на ручной запуск.
    if not cache.add(EXPORT_LOCK_KEY, "1", EXPORT_LOCK_TTL):
        raise HikBrowserExportError(
            "Выгрузка Hik уже выполняется в другом процессе — повторный запуск пропущен."
        )

    try:
        return _run_export(config, p_factory=sync_playwright, start=start_date, end=end, download_dir=download_dir)
    finally:
        cache.delete(EXPORT_LOCK_KEY)


def _run_export(
    config: HikBrowserExportConfig,
    *,
    p_factory,
    start: date,
    end: date,
    download_dir: Path,
) -> Path:
    start_date = start
    with p_factory() as p:
        browser = p.chromium.launch(**launch_kwargs(headless=config.headless))
        context = browser.new_context(**context_kwargs(accept_downloads=True))
        page = context.new_page()

        try:
            _login(page, config)
            _navigate_to_records(page, config)
            _set_date_range(page, start_date, end)
            _click_search(page)
            raw_path = _trigger_export(page, config.timeout_ms, download_dir)
        except HikBrowserExportError:
            if config.debug:
                shot, html = _save_debug_artifacts(page, download_dir)
                logger.error("Hik debug saved: %s %s url=%s", shot, html, page.url)
            raise
        except BrowserTokenFetchError as e:
            raise HikBrowserExportError(str(e)) from e
        except Exception as e:
            if config.debug:
                shot, html = _save_debug_artifacts(page, download_dir)
                raise HikBrowserExportError(
                    f"{e} (url={page.url}, screenshot={shot}, html={html})"
                ) from e
            raise HikBrowserExportError(f"{e} (url={page.url})") from e
        finally:
            browser.close()

    return _extract_xlsx_from_download(raw_path)


def fetch_hik_xlsx_for_date(config: HikBrowserExportConfig, target_date: date) -> Path:
    return fetch_hik_xlsx_export(config, start_date=target_date, end_date=target_date)
