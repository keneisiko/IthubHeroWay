from django.conf import settings
from django.db import connection
from django.utils import timezone
from rest_framework import permissions, views
from rest_framework.response import Response

import requests
from celery import current_app
from django.core.cache import cache


def _db_ok() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        return False


def _redis_ok() -> bool:
    try:
        cache.set("health:ping", "ok", 5)
        return cache.get("health:ping") == "ok"
    except Exception:
        return False


def _celery_ok() -> bool:
    try:
        inspect = current_app.control.inspect(timeout=1.5)
        ping = inspect.ping()
        return bool(ping)
    except Exception:
        return False


def _lxp_ok() -> bool:
    url = getattr(settings, "LXP_VERIFY_URL", "") or ""
    if not url:
        return True
    try:
        resp = requests.get(url, timeout=3)
        return resp.status_code < 500
    except requests.RequestException:
        return False


class HealthView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        checks = {
            "db": _db_ok(),
            "redis": _redis_ok(),
            "celery": _celery_ok(),
        }
        status_text = "ok" if all(checks.values()) else "degraded"
        return Response({"status": status_text, "checks": checks, "ts": timezone.now().isoformat()})


class ReadyView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        checks = {
            "db": _db_ok(),
            "redis": _redis_ok(),
            "lxp": _lxp_ok(),
        }
        status_text = "ready" if all(checks.values()) else "not_ready"
        return Response({"status": status_text, "checks": checks, "ts": timezone.now().isoformat()})

