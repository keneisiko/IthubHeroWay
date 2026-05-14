from pathlib import Path
import json
import os
from datetime import timedelta

from .rating_coefficients import QUESTS_REWARDS, RATING_DRIVE, RATING_KP, RATING_LIMITS

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = "change-me-in-prod"

DEBUG = True

ALLOWED_HOSTS: list[str] = ["*"]

INSTALLED_APPS = [
    "jazzmin",
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
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
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
STATICFILES_DIRS = [BASE_DIR / "staticfiles"] if (BASE_DIR / "staticfiles").exists() else []
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

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

JAZZMIN_SETTINGS = {
    "site_title": "IThub Admin",
    "site_header": "IThub Hero Path",
    "site_brand": "Hero Path",
    "welcome_sign": "Панель управления Path of Hero",
    "copyright": "IThub",
    "theme": "darkly",
    "show_sidebar": True,
    "navigation_expanded": True,
    "order_with_respect_to": [
        "accounts",
        "quests",
        "progress",
        "badges",
        "shop",
        "social",
    ],
    "custom_links": {
        "accounts": [
            {"name": "Кураторский дашборд", "url": "admin-curator-dashboard", "icon": "fas fa-user-check"},
            {"name": "Дашборд тьютора", "url": "admin-tutor-dashboard", "icon": "fas fa-user-graduate"},
            {"name": "Дашборд штаба", "url": "admin-hq-dashboard", "icon": "fas fa-flag"},
        ],
    },
    "icons": {
        "accounts.User": "fas fa-users",
        "accounts.Squad": "fas fa-people-group",
        "quests.Quest": "fas fa-scroll",
        "quests.SeasonalEvent": "fas fa-calendar-days",
        "quests.SquadLeaderboardSnapshot": "fas fa-ranking-star",
        "progress.RatingLog": "fas fa-chart-line",
        "shop.ShopItem": "fas fa-store",
        "badges.Badge": "fas fa-award",
        "social.Duel": "fas fa-hand-fist",
    },
    "custom_css": "admin/css/custom_admin.css",
}

# Cache TTLs (seconds)
LEADERBOARD_CACHE_TTL = 300  # 5 minutes
PROFILE_CACHE_TTL = 60       # 1 minute

# Integrations
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
LXP_VERIFY_URL = os.getenv("LXP_VERIFY_URL", "")
YOUGILE_API_URL = os.getenv("YOUGILE_API_URL", "")
YOUGILE_API_TOKEN = os.getenv("YOUGILE_API_TOKEN", "")
LXP_API_TOKEN = os.getenv("LXP_API_TOKEN", "")

LXP_GRAPHQL_ENDPOINT = os.getenv("LXP_GRAPHQL_ENDPOINT", "")
LXP_BOT_EMAIL = os.getenv("LXP_BOT_EMAIL", "")
LXP_BOT_PASSWORD = os.getenv("LXP_BOT_PASSWORD", "")
LXP_TOKEN_TTL_SECONDS = int(os.getenv("LXP_TOKEN_TTL_HOURS", "23")) * 60 * 60
LXP_USE_BROWSER_TOKEN_BOT = os.getenv("LXP_USE_BROWSER_TOKEN_BOT", "0").lower() in {"1", "true", "yes"}
LXP_WEB_BASE_URL = os.getenv("LXP_WEB_BASE_URL", "https://newlxp.ru")
LXP_WEB_LOGIN_URL = os.getenv("LXP_WEB_LOGIN_URL", LXP_WEB_BASE_URL)
LXP_BROWSER_GRAPHQL_HOST = os.getenv("LXP_BROWSER_GRAPHQL_HOST", "api.newlxp.ru")
LXP_BROWSER_HEADLESS = os.getenv("LXP_BROWSER_HEADLESS", "1").lower() in {"1", "true", "yes"}
LXP_BROWSER_TIMEOUT_MS = int(os.getenv("LXP_BROWSER_TIMEOUT_MS", "60000"))

# Ограничения объёма снимка LXP (цепочка getMe → группы → дисциплины → studentDiscipline)
LXP_SNAPSHOT_MAX_SUBORGS = int(os.getenv("LXP_SNAPSHOT_MAX_SUBORGS", "20"))
LXP_SNAPSHOT_MAX_GROUPS = int(os.getenv("LXP_SNAPSHOT_MAX_GROUPS", "50"))
LXP_SNAPSHOT_DISCIPLINES_PER_QUERY = int(os.getenv("LXP_SNAPSHOT_DISCIPLINES_PER_QUERY", "8"))

# HikCentral / Hik-Connect OpenAPI (Artemis), подпись x-ca-signature
HIK_HOST = os.getenv("HIK_HOST", "").strip()
HIK_PORT = int(os.getenv("HIK_PORT", "443"))
HIK_APP_KEY = os.getenv("HIK_APP_KEY", "").strip()
HIK_APP_SECRET = os.getenv("HIK_APP_SECRET", "").strip()
HIK_REQUEST_TIMEOUT = int(os.getenv("HIK_REQUEST_TIMEOUT", "30"))
HIK_MAX_RETRIES = int(os.getenv("HIK_MAX_RETRIES", "3"))
HIK_SSL_VERIFY = os.getenv("HIK_SSL_VERIFY", "1").lower() in {"1", "true", "yes"}
HIK_ARTEMIS_EVENT_RECORDS_PATH = os.getenv(
    "HIK_ARTEMIS_EVENT_RECORDS_PATH",
    "/artemis/api/event/v1/eventRecords/pages",
).strip()
HIK_SIGNATURE_DASH_HEADERS = os.getenv("HIK_SIGNATURE_DASH_HEADERS", "1").lower() in {"1", "true", "yes"}
HIK_SIGNATURE_HEADERS = os.getenv(
    "HIK_SIGNATURE_HEADERS",
    "x-ca-key,x-ca-nonce,x-ca-timestamp",
)
HIK_ARTEMIS_PERSON_PATH = os.getenv("HIK_ARTEMIS_PERSON_PATH", "").strip()
HIK_FETCH_LOOKBACK_HOURS = int(os.getenv("HIK_FETCH_LOOKBACK_HOURS", "2"))
HIK_PAGE_SIZE = int(os.getenv("HIK_PAGE_SIZE", "100"))
HIK_PROCESS_BATCH = int(os.getenv("HIK_PROCESS_BATCH", "8000"))
HIK_FETCH_ENABLED = (
    bool(HIK_HOST and HIK_APP_KEY and HIK_APP_SECRET)
    and os.getenv("HIK_FETCH_ENABLED", "1").lower() in {"1", "true", "yes"}
)

def _hk_extra():
    raw = os.getenv("HIK_EVENT_QUERY_EXTRA_JSON", "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


HIK_EVENT_QUERY_EXTRA = _hk_extra()
# Формат времени в теле запроса к HikCentral (зависит от версии платформы).
HIK_ARTEMIS_TIME_FORMAT = os.getenv(
    "HIK_ARTEMIS_TIME_FORMAT",
    "%Y-%m-%dT%H:%M:%S.000",
)

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

# LXP: TTL токена задаётся LXP_TOKEN_TTL_SECONDS (~23 ч) и совпадает с Redis TTL кеша.
# refresh-lxp-token за 15 мин до снимка; fetch дополнительно вызывает refresh синхронно в начале задачи.
CELERY_BEAT_SCHEDULE = {
    "fetch-lxp-snapshot-daily": {
        "task": "apps.integrations.tasks.fetch_lxp_snapshot",
        "schedule": crontab(hour=2, minute=0),
    },
    "refresh-lxp-token": {
        "task": "apps.integrations.tasks.refresh_lxp_token",
        "schedule": crontab(hour=1, minute=45),
    },
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
    "fetch-hik-events-hourly": {
        "task": "apps.integrations.tasks.fetch_hik_events",
        "schedule": crontab(minute=5),
    },
    "process-hik-events-daily": {
        "task": "apps.integrations.tasks.process_hik_events_daily",
        "schedule": crontab(hour=20, minute=0),
    },
}



