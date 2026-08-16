"""Настройки продакшена.

Все секреты приходят из окружения. Модуль намеренно падает при старте,
если обязательная переменная не задана: молча стартовать с dev-ключом опаснее,
чем не стартовать вообще.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import _env_bool, _env_int, _env_list


def _required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ImproperlyConfigured(
            f"Переменная окружения {name} обязательна при DJANGO_SETTINGS_MODULE=hero_path.settings.prod"
        )
    return value


SECRET_KEY = _required("SECRET_KEY")

DEBUG = False

ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS обязателен в продакшене (список хостов через запятую)")

CORS_ALLOWED_ORIGINS = _env_list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = _env_list("CSRF_TRUSTED_ORIGINS", CORS_ALLOWED_ORIGINS)

# HTTPS и куки. SECURE_SSL_REDIRECT можно выключить, если TLS терминируется на балансировщике
# и он же редиректит http→https.
SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # фронт читает csrftoken из cookie

SECURE_HSTS_SECONDS = _env_int("SECURE_HSTS_SECONDS", 60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = _env_bool("SECURE_HSTS_PRELOAD", False)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
