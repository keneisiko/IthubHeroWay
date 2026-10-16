"""Вход в бизнес-систему портала Hik Connect.

Обычный вход на портал больше не открывает бизнес-систему: 16 октября 2026
портал обновил фронт, и после логина аккаунт попадает на личный кабинет
(`/common/personal/DeviceManagement`), где раздела контроля доступа нет.
Запросы к API записей в таком состоянии получают
`{"errorCode":"VMS002004","message":"You need login first."}` — сессия
бизнес-системы не установлена.

Сам портал открывает её в два шага, и они восстановлены здесь по его коду:

1. `POST /customer/proxy/ccfauth/public/user/v1/account/hcb` — отдаёт
   `sessionId` бизнес-сессии и список систем аккаунта (`hcbInfoList`);
2. переход на маршрут `#/freeLogin` с параметрами `sessionId`, `account`
   и `chooseTenantId` (это `systemId` системы) — после него cookies домена
   API становятся авторизованными.

Оба адреса вынесены в настройки: портал уже менялся и поменяется снова,
и тогда их надо будет поправить, а не искать по коду заново. Как искать —
описано в `docs/HIKCENTRAL.md`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

from django.conf import settings

logger = logging.getLogger(__name__)

# Сколько ждать, пока портал отработает переход на freeLogin.
FREE_LOGIN_SETTLE_MS = 8_000
REQUEST_TIMEOUT_MS = 30_000


class HikBusinessLoginError(RuntimeError):
    """Не удалось войти в бизнес-систему портала."""


@dataclass(frozen=True)
class BusinessSystem:
    system_id: str
    system_name: str
    account: str


def _login_origin() -> str:
    """Схема и домен страницы входа: к ним относительны оба адреса шага."""
    url = getattr(settings, "HIK_WEB_LOGIN_URL", "") or ""
    parts = urlsplit(url)
    if not parts.scheme or not parts.hostname:
        raise HikBusinessLoginError(f"Не разобрать HIK_WEB_LOGIN_URL: {url!r}")
    return f"{parts.scheme}://{parts.netloc}"


def hcb_info_url() -> str:
    path = getattr(settings, "HIK_WEB_HCB_INFO_PATH", "")
    if not path:
        raise HikBusinessLoginError("Не задан HIK_WEB_HCB_INFO_PATH")
    return f"{_login_origin()}{path}"


def free_login_url(system: BusinessSystem, session_id: str) -> str:
    template = getattr(settings, "HIK_WEB_FREE_LOGIN_PATH", "")
    if not template:
        raise HikBusinessLoginError("Не задан HIK_WEB_FREE_LOGIN_PATH")
    return (
        f"{_login_origin()}{template}"
        f"?sessionId={quote(session_id)}"
        f"&account={quote(system.account)}"
        f"&chooseTenantId={quote(system.system_id)}"
        f"&isSimpleBusiness=true"
    )


def fetch_business_systems(page) -> tuple[str, list[BusinessSystem]]:
    """Спросить портал, какие бизнес-системы есть у аккаунта.

    Запрос идёт из браузера: он несёт cookies и заголовки страницы, а
    собирать их заново значило бы повторять работу портала.
    """
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

    error_code = str(body.get("errorCode", "")).strip()
    if error_code and error_code != "0":
        raise HikBusinessLoginError(
            f"Портал отказал в списке систем ({error_code}): {body.get('message') or ''}"
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
        raise HikBusinessLoginError("В ответе портала нет sessionId бизнес-сессии")
    if not systems:
        raise HikBusinessLoginError(
            "У аккаунта нет ни одной бизнес-системы: проверьте, что он добавлен "
            "в организацию колледжа в HikCentral"
        )
    return session_id, systems


def pick_system(systems: list[BusinessSystem]) -> BusinessSystem:
    """Какую систему открывать, если их несколько."""
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
        # Молча брать первую нельзя: у аккаунта может быть доступ к нескольким
        # организациям, и забор пошёл бы по чужим проходам.
        names = ", ".join(s.system_name for s in systems)
        raise HikBusinessLoginError(
            f"У аккаунта несколько бизнес-систем ({names}). "
            "Укажите нужную в HIK_WEB_SYSTEM_NAME."
        )
    return systems[0]


def enter_business_system(page) -> BusinessSystem:
    """Открыть бизнес-систему, чтобы запросы к API стали авторизованными."""
    session_id, systems = fetch_business_systems(page)
    system = pick_system(systems)

    logger.info(
        "hik_business_login: вхожу в систему «%s» (%s)", system.system_name, system.system_id
    )
    page.goto(free_login_url(system, session_id), wait_until="domcontentloaded")
    page.wait_for_timeout(FREE_LOGIN_SETTLE_MS)
    try:
        page.wait_for_load_state("networkidle", timeout=25_000)
    except Exception:
        # Портал догружает модули в фоне; для сессии это не обязательно.
        logger.debug("hik_business_login: сеть не успокоилась, продолжаю")
    return system
