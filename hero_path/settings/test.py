"""Настройки тестового прогона.

Кеш — locmem, чтобы тесты не требовали живого Redis. Инвалидация кеша в коде
идёт через apps.operations.services.cache, который умеет работать без
django_redis-специфичного delete_pattern.
"""

from .base import *  # noqa: F401,F403
from .base import _env_bool

DEBUG = False

# CI гоняет тесты на PostgreSQL (как в проде). Для быстрого локального прогона
# без поднятой базы: TEST_DATABASE_SQLITE=1.
if _env_bool("TEST_DATABASE_SQLITE", False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

SECRET_KEY = "test-secret-key"

ALLOWED_HOSTS = ["*"]

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "hero-path-tests",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Манифест whitenoise требует предварительного collectstatic — в тестах не нужен.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Внешние интеграции в тестах выключены: сеть недоступна и не нужна.
TELEGRAM_ALERTS_ENABLED = False
TELEGRAM_NOTIFICATIONS_ENABLED = False
HIK_DATA_MODE = "snapshot"
HIK_PROCESS_ENABLED = True
HIK_FETCH_ENABLED = False
LXP_USE_BROWSER_TOKEN_BOT = False
