"""Middleware для оповещения о необработанных ошибках Django."""

from __future__ import annotations

import traceback

from django.core.exceptions import PermissionDenied
from django.http import Http404

from apps.integrations.services.telegram_alert import send_alert_to_admin

_SKIP_PATH_PREFIXES = ("/health/", "/ready/", "/metrics/")


class TelegramErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, (Http404, PermissionDenied)):
            return None

        path = getattr(request, "path", "") or ""
        if any(path.startswith(p) for p in _SKIP_PATH_PREFIXES):
            return None

        user_repr = "anonymous"
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            user_repr = f"{user.pk} ({getattr(user, 'username', '')})"

        tb = traceback.format_exc()
        message = (
            f"URL: {path}\n"
            f"Method: {getattr(request, 'method', '')}\n"
            f"User: {user_repr}\n\n"
            f"Ошибка: {exception}\n\n"
            f"Трассировка:\n{tb}"
        )
        send_alert_to_admin(
            title="Internal Server Error (500)",
            message=message,
            error_type="critical",
            deduplicate_key=f"500:{path}:{type(exception).__name__}",
            is_critical=True,
        )
        return None
