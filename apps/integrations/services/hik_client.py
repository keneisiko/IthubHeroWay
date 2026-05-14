"""
Клиент HikCentral OpenAPI (Artemis).

Подпись: Base64(HMAC-SHA256(app_secret, stringToSign)).
Формат stringToSign и путь запросов настраиваются — у разных версий HCP могут отличаться суффиксы путей.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse, urlunparse

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class HikClientError(RuntimeError):
    pass


def _combine_host_port(host_raw: str, port: int) -> str:
    raw = (host_raw or "").strip().rstrip("/")
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    u = urlparse(raw)
    host = u.hostname or ""
    if not host:
        raise HikClientError("HIK_HOST: не удалось разобрать hostname")
    scheme = u.scheme or "https"
    effective_port = u.port if u.port else (int(port) if port else 443)
    if scheme == "https" and effective_port == 443:
        netloc = host
    else:
        netloc = f"{host}:{effective_port}"
    return urlunparse((scheme, netloc, "", "", "", ""))


def build_string_to_sign(
    *,
    method: str,
    accept: str,
    content_type: str,
    app_key: str,
    nonce: str,
    timestamp_ms: str,
    url_path: str,
    use_dash_ca_headers: bool = True,
) -> str:
    if use_dash_ca_headers:
        return (
            f"{method.upper()}\n"
            f"{accept}\n"
            f"{content_type}\n"
            f"x-ca-key:{app_key}\n"
            f"x-ca-nonce:{nonce}\n"
            f"x-ca-timestamp:{timestamp_ms}\n"
            f"{url_path}"
        )
    return (
        f"{method.upper()}\n"
        f"{accept}\n"
        f"{content_type}\n"
        f"x_ca_key:{app_key}\n"
        f"x_ca_nonce:{nonce}\n"
        f"x_ca_timestamp:{timestamp_ms}\n"
        f"{url_path}"
    )


def sign_request(app_secret: str, string_to_sign: str) -> str:
    key = app_secret.encode("utf-8")
    msg = string_to_sign.encode("utf-8")
    digest = hmac.new(key, msg, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


class HikCentralClient:
    def __init__(self):
        self.host_raw = getattr(settings, "HIK_HOST", "").strip()
        port = getattr(settings, "HIK_PORT", 443)
        try:
            self.port = int(port)
        except (TypeError, ValueError):
            self.port = 443
        self.app_key = getattr(settings, "HIK_APP_KEY", "").strip()
        self.app_secret = getattr(settings, "HIK_APP_SECRET", "").strip()
        self.timeout = int(getattr(settings, "HIK_REQUEST_TIMEOUT", 30))
        self.max_retries = int(getattr(settings, "HIK_MAX_RETRIES", 3))
        self.verify_ssl = getattr(settings, "HIK_SSL_VERIFY", True)
        self.event_records_path = getattr(
            settings,
            "HIK_ARTEMIS_EVENT_RECORDS_PATH",
            "/artemis/api/event/v1/eventRecords/pages",
        )
        self.use_dash_headers = getattr(settings, "HIK_SIGNATURE_DASH_HEADERS", True)
        self.signature_header_names = getattr(
            settings,
            "HIK_SIGNATURE_HEADERS",
            "x-ca-key,x-ca-nonce,x-ca-timestamp",
        )
        self.base = _combine_host_port(self.host_raw, self.port)
        self._configured = bool(self.base and self.app_key and self.app_secret)

    def _ensure_configured(self) -> None:
        if not self._configured:
            raise HikClientError("HIK_HOST / HIK_APP_KEY / HIK_APP_SECRET не заданы")

    def _headers(self, method: str, url_path_with_query: str, body_json: dict | None) -> dict[str, str]:
        accept = "application/json"
        content_type = "application/json"
        nonce = str(uuid.uuid4())
        timestamp_ms = str(int(time.time() * 1000))
        sts = build_string_to_sign(
            method=method,
            accept=accept,
            content_type=content_type,
            app_key=self.app_key,
            nonce=nonce,
            timestamp_ms=timestamp_ms,
            url_path=url_path_with_query,
            use_dash_ca_headers=self.use_dash_headers,
        )
        signature = sign_request(self.app_secret, sts)
        hdr: dict[str, str] = {
            "Accept": accept,
            "Content-Type": content_type,
            "x-ca-key": self.app_key,
            "x-ca-nonce": nonce,
            "x-ca-timestamp": timestamp_ms,
            "x-ca-signature": signature,
        }
        if self.signature_header_names:
            hdr["x-ca-signature-headers"] = self.signature_header_names
        return hdr

    def request_json(
        self,
        *,
        path: str,
        method: str = "POST",
        body: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """path должен начинаться с /artemis/"""
        self._ensure_configured()
        path_clean = "/" + path.strip().lstrip("/")
        qp = ""
        if params:
            qp = "?" + urlencode(params, safe=":+")
        url_path_for_sign = path_clean + qp
        url_body = body if body is not None else {}

        joined = self.base.rstrip("/") + path_clean + qp
        payload = json.dumps(url_body)

        delay = 1.0
        last_exc: BaseException | None = None
        for attempt in range(self.max_retries):
            try:
                headers = self._headers(method.upper(), url_path_for_sign, url_body)
                resp = requests.request(
                    method.upper(),
                    joined,
                    headers={**headers, "Content-Type": "application/json"},
                    data=payload,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
                if resp.status_code >= 500 and attempt + 1 < self.max_retries:
                    time.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
                if resp.status_code >= 400:
                    raise HikClientError(f"HTTP {resp.status_code}: {resp.text[:500]}")
                return resp.json() if resp.text else {}
            except requests.RequestException as e:
                last_exc = e
                if attempt + 1 < self.max_retries:
                    time.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
        raise HikClientError(str(last_exc) if last_exc else "HIK request failed")

    def _extract_event_rows(self, page_data: dict) -> list[dict]:
        root = page_data.get("data")
        if root is None:
            root = page_data
        if isinstance(root, dict):
            items = root.get("list") or root.get("rows") or root.get("eventList") or root.get("data")
            if isinstance(items, list):
                return items
            if isinstance(items, dict) and "list" in items:
                return items["list"] or []
        if isinstance(page_data.get("list"), list):
            return page_data["list"]
        return []

    def fetch_event_records_pages(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
        page_size: int = 100,
    ) -> list[dict]:
        """
        Выгружает записи постранично. Тело типично совместимо с eventRecords/pages —
        названия полей при необходимости подстройте через кастом в prod.
        """
        self._ensure_configured()
        tz = timezone.get_current_timezone()
        fmt = getattr(settings, "HIK_ARTEMIS_TIME_FORMAT", "%Y-%m-%dT%H:%M:%S.000")
        now = timezone.now()
        lookback = int(getattr(settings, "HIK_FETCH_LOOKBACK_HOURS", 2))
        s_lv = timezone.localtime(start if start is not None else now - timedelta(hours=lookback), tz)
        e_lv = timezone.localtime(end if end is not None else now, tz)
        start_time = s_lv.strftime(fmt)
        end_time = e_lv.strftime(fmt)

        all_rows: list[dict] = []
        page_no = 1
        extra = getattr(settings, "HIK_EVENT_QUERY_EXTRA", {})
        pg_size = min(max(page_size, 1), 500)
        while True:
            body = {
                "pageNo": page_no,
                "pageSize": pg_size,
                "startTime": start_time,
                "endTime": end_time,
                **extra,
            }
            resp = self.request_json(path=self.event_records_path, body=body)
            chunk = self._extract_event_rows(resp)
            all_rows.extend(chunk)
            total = resp.get("data", {})
            total_pages = (
                isinstance(total, dict)
                and (total.get("totalPage") or total.get("pages") or total.get("totalPages"))
                or resp.get("totalPage")
                or resp.get("totalPages")
            )
            if isinstance(total_pages, str) and total_pages.isdigit():
                total_pages = int(total_pages)
            if isinstance(total_pages, int) and page_no >= total_pages >= 1:
                break
            if not chunk:
                break
            page_no += 1
            if page_no > 3000:
                logger.warning("HikCentral: принудительный стоп после 3000 страниц")
                break
        return all_rows

    def get_person_stub(self, person_code: str) -> dict:
        lookup = getattr(settings, "HIK_ARTEMIS_PERSON_PATH", "").strip()
        if not lookup:
            return {}
        pc = {"personCode": person_code, **getattr(settings, "HIK_PERSON_QUERY_BODY", {})}
        return self.request_json(path=lookup, body=pc)
