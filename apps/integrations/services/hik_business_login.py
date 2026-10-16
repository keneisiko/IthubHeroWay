"""Открытие бизнес-системы портала Hik Connect.

Обычный вход на портал не даёт доступа к записям прохода. 16 октября 2026
портал обновил фронт: после логина аккаунт попадает на личный кабинет
(`/common/personal/DeviceManagement`), а запросы к API записей отвечают
`{"errorCode":"VMS002004","message":"You need login first."}` — сессия
бизнес-системы на домене API не установлена.

Как это делает сам портал (видно в сетевом журнале рабочей сессии): при
загрузке страницы портала SPA вызывает на домене API
`POST /hcc/resource/v1/login/loginafter`, и только после этого остальные
запросы авторизованы. Вызвать `loginafter` напрямую нельзя — он требует
параметров, которых мы не знаем («params node is not existed»), поэтому мы
не воспроизводим его, а даём порталу выполнить его сам: открываем страницу
портала и ждём.

Отсюда устройство модуля: **готовность проверяется делом**, а не ожиданием
вёрстки. После каждой попытки мы спрашиваем у API одну запись: пришёл
`errorCode: 0` — сессия готова; пришло «You need login first» — нет.
Такая проверка не зависит от того, как портал выглядит сегодня, а он
выглядит по-разному даже между двумя запусками подряд.

Попытки идут по возрастанию сложности:

1. вдруг сессия уже готова (бывает, если портал успел всё сделать сам);
2. открыть страницу портала — обычный путь, которым идёт человек;
3. открыть систему явно через маршрут `#/freeLogin` с `sessionId`,
   `account` и `chooseTenantId` — он нужен, когда у аккаунта несколько
   организаций и портал не знает, какую открывать.

Адреса и маршруты — в настройках: портал уже менялся и поменяется снова.
Как искать их заново, описано в `docs/HIKCENTRAL.md`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

from django.conf import settings

logger = logging.getLogger(__name__)

SETTLE_MS = 5_000
REQUEST_TIMEOUT_MS = 30_000
# Сессия поднимается не мгновенно: портал догружает модули и только потом
# зовёт loginafter. Одной проверки сразу после загрузки мало.
READY_ATTEMPTS = 6
READY_PAUSE_MS = 4_000
# Признак того, что сессия бизнес-системы не установлена.
NOT_LOGGED_IN_CODE = "VMS002004"


class HikBusinessLoginError(RuntimeError):
    """Не удалось открыть бизнес-систему портала."""


@dataclass(frozen=True)
class BusinessSystem:
    system_id: str
    system_name: str
    account: str


def _login_origin() -> str:
    url = getattr(settings, "HIK_WEB_LOGIN_URL", "") or ""
    parts = urlsplit(url)
    if not parts.scheme or not parts.hostname:
        raise HikBusinessLoginError(f"Не разобрать HIK_WEB_LOGIN_URL: {url!r}")
    return f"{parts.scheme}://{parts.netloc}"


def _setting(name: str) -> str:
    value = (getattr(settings, name, "") or "").strip()
    if not value:
        raise HikBusinessLoginError(f"Не задан {name}")
    return value


def hcb_info_url() -> str:
    return f"{_login_origin()}{_setting('HIK_WEB_HCB_INFO_PATH')}"


def portal_url() -> str:
    return f"{_login_origin()}{_setting('HIK_WEB_PORTAL_PATH')}"


def free_login_url(system: BusinessSystem, session_id: str) -> str:
    return (
        f"{_login_origin()}{_setting('HIK_WEB_FREE_LOGIN_PATH')}"
        f"?sessionId={quote(session_id)}"
        f"&account={quote(system.account)}"
        f"&chooseTenantId={quote(system.system_id)}"
        f"&isSimpleBusiness=true"
    )


def _records_url() -> str:
    base = (getattr(settings, "HIK_WEB_API_BASE", "") or "").rstrip("/")
    path = getattr(settings, "HIK_WEB_API_RECORDS_PATH", "") or ""
    if not base or not path:
        raise HikBusinessLoginError("Не заданы HIK_WEB_API_BASE / HIK_WEB_API_RECORDS_PATH")
    return f"{base}{path}"


def session_is_ready(page) -> bool:
    """Отвечает ли API записей делом.

    Единственная надёжная проверка готовности: вёрстка портала меняется, а
    этот ответ — нет. Запрос нарочно крошечный: одна запись, без фильтров.
    """
    try:
        response = page.request.post(
            _records_url(),
            data=json.dumps({"pageIndex": 1, "pageSize": 1}),
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "clientSource": "0",
            },
            timeout=REQUEST_TIMEOUT_MS,
        )
        body = json.loads(response.text())
    except Exception as exc:
        logger.debug("hik_business_login: проверка сессии не удалась: %s", type(exc).__name__)
        return False

    code = str(body.get("errorCode", "")).strip()
    if code == "0":
        return True
    if code == NOT_LOGGED_IN_CODE:
        return False
    logger.warning(
        "hik_business_login: API ответил кодом %s (%s)", code, body.get("message") or ""
    )
    return False


def _describe(value, depth: int = 0):
    """Форма ответа без значений: в нём бывают токены."""
    if depth > 3:
        return "..."
    if isinstance(value, dict):
        return {k: _describe(v, depth + 1) for k, v in list(value.items())[:12]}
    if isinstance(value, list):
        return [_describe(v, depth + 1) for v in value[:3]]
    if isinstance(value, str):
        return value if len(value) <= 40 else f"<{len(value)} знаков>"
    return value


def wait_until_ready(page, what: str) -> bool:
    """Подождать, пока API начнёт отвечать делом."""
    for attempt in range(1, READY_ATTEMPTS + 1):
        if session_is_ready(page):
            logger.info("hik_business_login: сессия открыта (%s, попытка %s)", what, attempt)
            return True
        if attempt < READY_ATTEMPTS:
            page.wait_for_timeout(READY_PAUSE_MS)
    return False


def fetch_business_systems(page) -> tuple[str, list[BusinessSystem]]:
    """Список бизнес-систем аккаунта и `sessionId` бизнес-сессии."""
    response = page.request.post(
        hcb_info_url(),
        data="{}",
        headers={"Content-Type": "application/json", "clientSource": "0"},
        timeout=REQUEST_TIMEOUT_MS,
    )
    text = response.text()
    try:
        body = json.loads(text)
    except ValueError as exc:
        raise HikBusinessLoginError(f"Портал вернул не JSON: {text[:120]}") from exc

    # Портал отвечает ошибками в двух обёртках: бизнес-сервисы кладут код
    # в errorCode, а служба авторизации — в resultCode с текстом в resultDes.
    # Вторую мы не разбирали, и «Unauthorized» выглядел как «нет sessionId».
    code = str(body.get("errorCode", "")).strip()
    if code and code != "0":
        raise HikBusinessLoginError(
            f"Портал отказал в списке систем ({code}): {body.get('message') or ''}"
        )

    result_code = str(body.get("resultCode", "")).strip()
    if result_code and result_code not in {"0", "200"}:
        hint = ""
        if "unauthoriz" in str(body.get("resultDes", "")).lower():
            # Портал держит одну активную сессию на аккаунт: вход из браузера
            # обесценивает сессию бота и наоборот.
            hint = (
                " Похоже, сессия входа уже недействительна. Частая причина — "
                "этим же аккаунтом вошли в портал из браузера: портал держит "
                "одну активную сессию. Выйдите из портала и повторите, а для "
                "постоянной работы заведите отдельный сервисный аккаунт."
            )
        raise HikBusinessLoginError(
            f"Портал не авторизовал запрос ({result_code}): "
            f"{body.get('resultDes') or ''}.{hint}"
        )

    data = body.get("data") or {}
    session_id = str(data.get("sessionId") or "")
    systems = [
        BusinessSystem(
            system_id=str(row.get("systemId") or ""),
            system_name=str(row.get("systemName") or ""),
            account=str(row.get("email") or row.get("username") or ""),
        )
        for row in (data.get("hcbInfoList") or [])
        if row.get("systemId")
    ]
    if not session_id:
        # Без текста ответа это тупик: непонятно, портал ли изменил формат,
        # или сессия входа уже не годится. Значения маскируются.
        raise HikBusinessLoginError(
            "В ответе портала нет sessionId бизнес-сессии. "
            f"Портал ответил: {_describe(body)}"
        )
    if not systems:
        raise HikBusinessLoginError(
            "У аккаунта нет ни одной бизнес-системы: проверьте, что он добавлен "
            "в организацию колледжа в HikCentral"
        )
    return session_id, systems


def pick_system(systems: list[BusinessSystem]) -> BusinessSystem:
    wanted = (getattr(settings, "HIK_WEB_SYSTEM_NAME", "") or "").strip().lower()
    if wanted:
        for system in systems:
            if system.system_name.strip().lower() == wanted:
                return system
        names = ", ".join(s.system_name for s in systems)
        raise HikBusinessLoginError(
            f"Система «{wanted}» у аккаунта не найдена. Доступные: {names}"
        )
    if len(systems) > 1:
        # Молча взять первую нельзя: у аккаунта может быть доступ к нескольким
        # организациям, и забор пошёл бы по чужим проходам.
        names = ", ".join(s.system_name for s in systems)
        raise HikBusinessLoginError(
            f"У аккаунта несколько бизнес-систем ({names}). "
            "Укажите нужную в HIK_WEB_SYSTEM_NAME."
        )
    return systems[0]


def _open(page, url: str, what: str) -> None:
    logger.info("hik_business_login: открываю %s", what)
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(SETTLE_MS)
    try:
        page.wait_for_load_state("networkidle", timeout=25_000)
    except Exception:
        # Портал догружает модули в фоне; для сессии это не обязательно.
        logger.debug("hik_business_login: сеть не успокоилась, продолжаю")


def ensure_business_session(page) -> None:
    """Добиться того, чтобы API записей отвечал, или объяснить, почему нет."""
    if session_is_ready(page):
        logger.info("hik_business_login: сессия уже готова")
        return

    # Обычный путь: страница портала, загружаясь, сама вызывает loginafter
    # на домене API — именно он и открывает сессию.
    _open(page, portal_url(), "страницу портала")
    if wait_until_ready(page, "страница портала"):
        return

    # Портал мог не понять, какую организацию открывать. Указываем явно.
    session_id, systems = fetch_business_systems(page)
    system = pick_system(systems)
    _open(page, free_login_url(system, session_id), f"систему «{system.system_name}»")
    if wait_until_ready(page, f"система «{system.system_name}»"):
        return

    raise HikBusinessLoginError(
        "API записей отвечает «нужно войти» даже после открытия системы "
        f"«{system.system_name}». Портал мог снова поменять вход — как искать "
        "новые адреса, описано в docs/HIKCENTRAL.md"
    )
