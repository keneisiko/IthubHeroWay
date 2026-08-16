"""Клиент внутреннего API портала Hik Connect (записи прохода).

OpenAPI-ключей у колледжа нет, но портал — обычное SPA, которое ходит в свой
HTTP API. Браузер нужен только чтобы получить сессионные cookies
(см. `hik_session.py`); дальше работают обычные HTTP-запросы, независимые
от вёрстки портала.

Контракт снят с живой сессии 2026-08-15 (`manage.py probe_hik_web`):

    POST https://team.hikcentralconnectru.com/hcc/hccacs/v1/event/certificateRecords/search
    Заголовки: Content-Type: application/json, clientSource: 0
    Авторизация: только cookies, заголовка Authorization нет
    Тело: {"pageIndex":1,"pageSize":100,"searchCriteria":{
             "beginTime":"...+03:00","endTime":"...+03:00","type":0,
             "eventTypes":"","elementIDs":"","searchType":0,
             "cardNumber":"","personCondition":{},"swipeAuthResult":0}}
    Ответ: {"errorCode":"0","data":{"totalNum":N,"recordList":[...]}}

Особенности данных, проверенные на выборке из ~115 000 записей за апрель–июнь:

* `recordGuid` — стабильный уникальный идентификатор события. Самодельные хеши
  по содержимому строки больше не нужны.
* `cardNumber` пуст во всех записях. Привязка к студенту идёт через
  `personInfo.baseInfo.email` (совпадает с почтой из LXP) и `personCode`.
* `direction`: 1 — вход, 2 — выход. Проверено сопоставлением с именами
  устройств: direction=1 приходит только с турникета «Вход», 2 — только
  с «Выход».
* `occurTime` — UTC (суффикс Z), `deviceTime` — местное время с `+03:00`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Iterator

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DIRECTION_ENTRY = 1
DIRECTION_EXIT = 2

SWIPE_AUTH_OK = 1

# Предохранитель от бесконечного цикла, если портал начнёт врать в totalNum.
MAX_PAGES = 500


class HikWebClientError(RuntimeError):
    """Портал ответил ошибкой или недоступен."""


class HikWebAuthError(HikWebClientError):
    """Сессия недействительна: нужен повторный логин через браузер."""


@dataclass(frozen=True)
class HikWebConfig:
    base_url: str
    records_path: str
    page_size: int
    timeout: int

    @property
    def records_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.records_path.lstrip('/')}"


def config_from_settings() -> HikWebConfig:
    return HikWebConfig(
        base_url=(getattr(settings, "HIK_WEB_API_BASE", "") or "").strip(),
        records_path=(
            getattr(settings, "HIK_WEB_API_RECORDS_PATH", "")
            or "/hcc/hccacs/v1/event/certificateRecords/search"
        ).strip(),
        page_size=int(getattr(settings, "HIK_WEB_API_PAGE_SIZE", 100)),
        timeout=int(getattr(settings, "HIK_WEB_API_TIMEOUT", 60)),
    )


def _iso_local(value: datetime) -> str:
    """Портал ждёт время со смещением (`2026-06-29T19:05:46+03:00`)."""
    if value.tzinfo is None:
        raise ValueError("Границы диапазона должны быть с таймзоной")
    return value.isoformat()


def build_search_payload(start: datetime, end: datetime, *, page: int, page_size: int) -> dict:
    return {
        "pageIndex": page,
        "pageSize": page_size,
        "searchCriteria": {
            "beginTime": _iso_local(start),
            "endTime": _iso_local(end),
            "type": 0,
            "eventTypes": "",
            "elementIDs": "",
            "searchType": 0,
            "cardNumber": "",
            "personCondition": {},
            "swipeAuthResult": 0,
        },
    }


def normalize_record(raw: dict) -> dict | None:
    """Привести запись портала к строке, понятной `save_hik_row_as_event`.

    Возвращает None для записей без идентификатора или без времени — такие
    события нельзя ни дедуплицировать, ни сопоставить с расписанием.
    """
    if not isinstance(raw, dict):
        return None

    event_id = str(raw.get("recordGuid") or "").strip()
    if not event_id:
        return None

    # deviceTime — местное время устройства со смещением, occurTime — UTC.
    # Предпочитаем deviceTime: он ближе к тому, что видит человек в портале.
    event_time = str(raw.get("deviceTime") or raw.get("occurTime") or "").strip()
    if not event_time:
        return None

    person = raw.get("personInfo") or {}
    base = person.get("baseInfo") or {}

    person_code = str(base.get("personCode") or "").strip()
    email = str(base.get("email") or "").strip().lower()
    full_name = " ".join(
        part for part in (base.get("lastName"), base.get("firstName")) if part
    ).strip()

    try:
        direction = int(raw.get("direction") or 0)
    except (TypeError, ValueError):
        direction = 0

    door = str(raw.get("elementName") or raw.get("deviceName") or "").strip()

    return {
        "eventId": event_id,
        "personCode": person_code,
        "personEmail": email,
        "personId": str(person.get("id") or "").strip(),
        "personName": full_name,
        "eventTime": event_time,
        # Внутренний тип события; опоздание вычисляется позже по расписанию.
        "eventType": "access",
        "doorName": door,
        "direction": direction,
        "isEntry": direction == DIRECTION_ENTRY,
        "authOk": raw.get("swipeAuthResult") == SWIPE_AUTH_OK,
        "hikEventType": raw.get("eventType"),
        "cardNumber": str(raw.get("cardNumber") or "").strip(),
    }


class HikWebClient:
    """Постраничное чтение записей прохода по cookies сессии портала."""

    def __init__(
        self,
        cookies: dict[str, str],
        *,
        config: HikWebConfig | None = None,
        session: requests.Session | None = None,
    ):
        self.config = config or config_from_settings()
        if not self.config.base_url:
            raise HikWebClientError(
                "Не задан HIK_WEB_API_BASE. Получите его командой `manage.py probe_hik_web`."
            )
        self.session = session or requests.Session()
        self.session.cookies.update(cookies or {})

    def _post(self, payload: dict) -> dict:
        try:
            response = self.session.post(
                self.config.records_url,
                json=payload,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json",
                    "clientSource": "0",
                },
                timeout=self.config.timeout,
            )
        except requests.RequestException as exc:
            raise HikWebClientError(f"Портал недоступен: {exc}") from exc

        if response.status_code in {401, 403}:
            raise HikWebAuthError(
                f"Сессия портала недействительна (HTTP {response.status_code})"
            )
        if response.status_code >= 400:
            raise HikWebClientError(f"Портал ответил HTTP {response.status_code}")

        try:
            body = response.json()
        except ValueError as exc:
            raise HikWebClientError("Портал вернул не JSON") from exc

        error_code = str(body.get("errorCode", "")).strip()
        if error_code and error_code != "0":
            # Портал сообщает об истёкшей сессии кодом, а не статусом.
            message = str(body.get("message") or "")
            if "login" in message.lower() or "session" in message.lower():
                raise HikWebAuthError(f"Сессия портала истекла: {message}")
            raise HikWebClientError(f"Портал вернул ошибку {error_code}: {message}")

        data = body.get("data")
        if not isinstance(data, dict):
            raise HikWebClientError("В ответе портала нет блока data")
        return data

    def iter_raw_records(self, start: datetime, end: datetime) -> Iterator[dict]:
        """Пройти по всем страницам диапазона и отдать сырые записи."""
        page = 1
        seen = 0
        total = None

        while page <= MAX_PAGES:
            data = self._post(
                build_search_payload(start, end, page=page, page_size=self.config.page_size)
            )
            if total is None:
                total = int(data.get("totalNum") or 0)
                logger.info(
                    "hik_web: записей в диапазоне %s — %s", f"{start:%Y-%m-%d}..{end:%Y-%m-%d}", total
                )

            records = data.get("recordList") or []
            if not records:
                return

            for record in records:
                seen += 1
                yield record

            if total and seen >= total:
                return
            page += 1

        logger.warning("hik_web: достигнут предел в %s страниц, выгрузка оборвана", MAX_PAGES)

    def fetch_rows(self, start: datetime, end: datetime) -> list[dict]:
        """Нормализованные строки, готовые для `save_hik_row_as_event`."""
        return list(normalize_rows(self.iter_raw_records(start, end)))


def normalize_rows(raw_records: Iterable[dict]) -> Iterator[dict]:
    skipped = 0
    for raw in raw_records:
        row = normalize_record(raw)
        if row is None:
            skipped += 1
            continue
        yield row
    if skipped:
        logger.warning("hik_web: пропущено записей без id или времени: %s", skipped)
