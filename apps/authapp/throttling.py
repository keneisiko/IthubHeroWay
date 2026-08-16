"""Ограничение частоты попыток входа.

Вход проксирует пароль в LXP, то есть наш API — готовый инструмент для
перебора паролей от учебного портала. Ограничиваем в двух измерениях:

* по IP — чтобы один источник не перебирал пароли к разным аккаунтам;
* по логину — чтобы распределённый перебор не подбирал пароль к одному
  аккаунту с разных адресов.
"""

from __future__ import annotations

import hashlib

from rest_framework.throttling import SimpleRateThrottle


class LoginIPThrottle(SimpleRateThrottle):
    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class LoginIdentifierThrottle(SimpleRateThrottle):
    """Ограничение по конкретному логину, независимо от адреса запроса."""

    scope = "login_burst"

    def get_cache_key(self, request, view):
        raw = ""
        if isinstance(getattr(request, "data", None), dict):
            raw = str(request.data.get("login") or request.data.get("username") or "")
        raw = raw.strip().lower()
        if not raw:
            return None
        # Логин — это почта студента; в ключ кеша кладём хеш, а не сам адрес.
        digest = hashlib.sha256(raw.encode()).hexdigest()[:32]
        return self.cache_format % {"scope": self.scope, "ident": digest}
