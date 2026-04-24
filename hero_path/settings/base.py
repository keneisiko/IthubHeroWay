from pathlib import Path
import os
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = "change-me-in-prod"

DEBUG = True

ALLOWED_HOSTS: list[str] = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "django_prometheus",
    "corsheaders",
    "apps.accounts",
    "apps.progress",
    "apps.quests",
    "apps.badges",
    "apps.shop",
    "apps.social",
    "apps.integrations",
    "apps.notifications",
    "apps.operations",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "hero_path.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "hero_path.wsgi.application"
ASGI_APPLICATION = "hero_path.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "hero_path"),
        "USER": os.getenv("POSTGRES_USER", "hero_path"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "hero_path"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": int(os.getenv("POSTGRES_PORT", "5432")),
        "CONN_MAX_AGE": 60,
    }
}

AUTH_USER_MODEL = "accounts.User"

# Redis / cache / sessions
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "TIMEOUT": 60,
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Hero Path API",
    "DESCRIPTION": "Gamification backend API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOWED_ORIGINS: list[str] = [
    "http://localhost:3000",
]

# Cache TTLs (seconds)
LEADERBOARD_CACHE_TTL = 300  # 5 minutes
PROFILE_CACHE_TTL = 60       # 1 minute

# Integrations
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
LXP_VERIFY_URL = os.getenv("LXP_VERIFY_URL", "")
YOUGILE_API_URL = os.getenv("YOUGILE_API_URL", "")
YOUGILE_API_TOKEN = os.getenv("YOUGILE_API_TOKEN", "")
LXP_API_TOKEN = os.getenv("LXP_API_TOKEN", "")

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
        send_default_pii=False,
    )

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = TIME_ZONE

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "recalculate_rating_daily": {
        "task": "apps.progress.tasks.recalculate_rating_daily",
        "schedule": crontab(hour=6, minute=0),
    },
    "recalculate_pillars_weekly": {
        "task": "apps.progress.tasks.recalculate_pillars_weekly",
        "schedule": crontab(hour=22, minute=0, day_of_week="sun"),
    },
    "send_daily_quest": {
        "task": "apps.quests.tasks.send_daily_quest",
        "schedule": crontab(hour=7, minute=30),
    },
    "check_strikes_daily": {
        "task": "apps.progress.tasks.check_strikes_daily",
        "schedule": crontab(hour=23, minute=0),
    },
    "check_badges_weekly": {
        "task": "apps.badges.tasks.check_badges_weekly",
        "schedule": crontab(hour=21, minute=0, day_of_week="sun"),
    },
    "squad_digest_friday": {
        "task": "apps.notifications.tasks.squad_digest_friday",
        "schedule": crontab(hour=17, minute=0, day_of_week="fri"),
    },
    "curator_report_monday": {
        "task": "apps.notifications.tasks.curator_report_monday",
        "schedule": crontab(hour=9, minute=0, day_of_week="mon"),
    },
}



