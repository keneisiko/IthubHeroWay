import json
import os
from datetime import timedelta
from pathlib import Path

from .rating_coefficients import QUESTS_REWARDS, RATING_DRIVE, RATING_KP, RATING_LIMITS, RATING_YEAR

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _env_int(name: str, default: int) -> int:
    """int из env; пустая строка из docker-compose → default."""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


_TRUTHY = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool) -> bool:
    """bool из env; пустая строка из docker-compose → default."""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in _TRUTHY


def _env_list(name: str, default: list[str] | None = None) -> list[str]:
    """Список через запятую из env; пустая строка → default."""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return list(default or [])
    return [item.strip() for item in str(raw).split(",") if item.strip()]


# Значения ниже безопасны только для локальной разработки.
# Профили dev/prod/test переопределяют их: см. hero_path/settings/prod.py.
SECRET_KEY = os.getenv("SECRET_KEY", "") or "insecure-dev-key-do-not-use-in-production"

DEBUG = _env_bool("DEBUG", False)

ALLOWED_HOSTS: list[str] = _env_list("ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

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
    "apps.schedule",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "hero_path.middleware.TelegramErrorMiddleware",
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
        "PORT": _env_int("POSTGRES_PORT", 5432),
        # Держать соединение дольше выгодно, но каждое живое соединение занимает
        # слот в max_connections Postgres: воркеры gunicorn × реплики × 1 соединение.
        # За пулером (pgbouncer в transaction mode) ставить 0.
        "CONN_MAX_AGE": _env_int("DB_CONN_MAX_AGE", 60),
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

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(os.getenv("STATIC_ROOT") or (BASE_DIR / "static"))
STATICFILES_DIRS = [BASE_DIR / "staticfiles"] if (BASE_DIR / "staticfiles").exists() else []

# Django 5.1 удалил STATICFILES_STORAGE/DEFAULT_FILE_STORAGE — только STORAGES.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Не стандартный CompressedManifestStaticFilesStorage: jazzmin просит
    # у {% static %} каталог темы, которого в манифесте нет, и админка
    # отдавала 500. См. hero_path/storages.py.
    "staticfiles": {"BACKEND": "hero_path.storages.ForgivingManifestStaticFilesStorage"},
}

MEDIA_URL = "/media/"
# В проде каталог смонтирован томом: аватары не должны жить внутри образа,
# иначе пропадают при первом же обновлении контейнера.
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT") or (BASE_DIR / "media"))

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
    # Логин проксирует пароль в LXP, поэтому без ограничения частоты через наш
    # API можно перебирать чужие пароли от учебного портала.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": os.getenv("THROTTLE_LOGIN", "10/min"),
        "login_burst": os.getenv("THROTTLE_LOGIN_BURST", "60/hour"),
        "webhook": os.getenv("THROTTLE_WEBHOOK", "120/min"),
        "heavy": os.getenv("THROTTLE_HEAVY", "12/min"),
    },
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

CORS_ALLOWED_ORIGINS: list[str] = _env_list(
    "CORS_ALLOWED_ORIGINS",
    ["http://localhost:3000", "http://localhost:5173"],
)
CSRF_TRUSTED_ORIGINS: list[str] = _env_list("CSRF_TRUSTED_ORIGINS", CORS_ALLOWED_ORIGINS)

JAZZMIN_SETTINGS = {
    "site_title": "Админ-панель IThub",
    "site_header": "Путь героя IThub",
    "site_brand": "Путь героя",
    "welcome_sign": "Добро пожаловать в панель управления «Путь героя»",
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
        "integrations",
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
ENVIRONMENT_NAME = os.getenv("ENVIRONMENT_NAME", "development")
TELEGRAM_ALERTS_ENABLED = _env_bool("TELEGRAM_ALERTS_ENABLED", True)
TELEGRAM_ALERT_DEDUP_TTL = _env_int("TELEGRAM_ALERT_DEDUP_TTL", 3600)
LXP_VERIFY_URL = os.getenv("LXP_VERIFY_URL", "")
YOUGILE_API_URL = os.getenv("YOUGILE_API_URL", "")
YOUGILE_API_TOKEN = os.getenv("YOUGILE_API_TOKEN", "")
# Без секрета вебхук YouGile отклоняет все запросы: он влияет на рейтинг,
# поэтому открытым по умолчанию быть не должен.
YOUGILE_WEBHOOK_SECRET = os.getenv("YOUGILE_WEBHOOK_SECRET", "")
LXP_API_TOKEN = os.getenv("LXP_API_TOKEN", "")

LXP_GRAPHQL_ENDPOINT = os.getenv("LXP_GRAPHQL_ENDPOINT", "")
LXP_BOT_EMAIL = os.getenv("LXP_BOT_EMAIL", "")
LXP_BOT_PASSWORD = os.getenv("LXP_BOT_PASSWORD", "")
LXP_TOKEN_TTL_SECONDS = _env_int("LXP_TOKEN_TTL_HOURS", 23) * 60 * 60
LXP_USE_BROWSER_TOKEN_BOT = _env_bool("LXP_USE_BROWSER_TOKEN_BOT", False)
LXP_WEB_BASE_URL = os.getenv("LXP_WEB_BASE_URL", "https://newlxp.ru")
LXP_WEB_LOGIN_URL = os.getenv("LXP_WEB_LOGIN_URL", LXP_WEB_BASE_URL)
LXP_BROWSER_GRAPHQL_HOST = os.getenv("LXP_BROWSER_GRAPHQL_HOST", "api.newlxp.ru")
LXP_BROWSER_HEADLESS = _env_bool("LXP_BROWSER_HEADLESS", True)
LXP_BROWSER_TIMEOUT_MS = _env_int("LXP_BROWSER_TIMEOUT_MS", 60_000)

# Ограничения объёма снимка LXP (цепочка getMe → группы → дисциплины → studentDiscipline)
LXP_SNAPSHOT_MAX_SUBORGS = _env_int("LXP_SNAPSHOT_MAX_SUBORGS", 20)
LXP_SNAPSHOT_MAX_GROUPS = _env_int("LXP_SNAPSHOT_MAX_GROUPS", 50)
LXP_SNAPSHOT_DISCIPLINES_PER_QUERY = _env_int("LXP_SNAPSHOT_DISCIPLINES_PER_QUERY", 8)

# HikCentral / Hik-Connect OpenAPI (Artemis), подпись x-ca-signature
HIK_HOST = os.getenv("HIK_HOST", "").strip()
HIK_PORT = _env_int("HIK_PORT", 443)
HIK_APP_KEY = os.getenv("HIK_APP_KEY", "").strip()
HIK_APP_SECRET = os.getenv("HIK_APP_SECRET", "").strip()
HIK_REQUEST_TIMEOUT = _env_int("HIK_REQUEST_TIMEOUT", 30)
HIK_MAX_RETRIES = _env_int("HIK_MAX_RETRIES", 3)
HIK_SSL_VERIFY = _env_bool("HIK_SSL_VERIFY", True)
HIK_ARTEMIS_EVENT_RECORDS_PATH = os.getenv(
    "HIK_ARTEMIS_EVENT_RECORDS_PATH",
    "/artemis/api/event/v1/eventRecords/pages",
).strip()
HIK_SIGNATURE_DASH_HEADERS = _env_bool("HIK_SIGNATURE_DASH_HEADERS", True)
HIK_SIGNATURE_HEADERS = os.getenv(
    "HIK_SIGNATURE_HEADERS",
    "x-ca-key,x-ca-nonce,x-ca-timestamp",
)
HIK_ARTEMIS_PERSON_PATH = os.getenv("HIK_ARTEMIS_PERSON_PATH", "").strip()
HIK_FETCH_LOOKBACK_HOURS = _env_int("HIK_FETCH_LOOKBACK_HOURS", 2)
HIK_PAGE_SIZE = _env_int("HIK_PAGE_SIZE", 100)
HIK_PROCESS_BATCH = _env_int("HIK_PROCESS_BATCH", 8000)
HIK_FETCH_ENABLED = bool(HIK_HOST and HIK_APP_KEY and HIK_APP_SECRET) and _env_bool(
    "HIK_FETCH_ENABLED", True
)

# api — OpenAPI; browser — Playwright XLSX с hik-connectru; snapshot — ручной JSON/XLSX; off — без Hik
_hik_mode_raw = os.getenv("HIK_DATA_MODE", "").strip().lower()
_hik_browser_export = _env_bool("HIK_USE_BROWSER_EXPORT", False)
if _hik_mode_raw in {"api", "snapshot", "off", "browser"}:
    HIK_DATA_MODE = _hik_mode_raw
elif _hik_browser_export:
    HIK_DATA_MODE = "browser"
elif HIK_FETCH_ENABLED:
    HIK_DATA_MODE = "api"
else:
    HIK_DATA_MODE = "snapshot"

HIK_USE_BROWSER_EXPORT = _hik_browser_export or HIK_DATA_MODE == "browser"
HIK_WEB_LOGIN_URL = os.getenv(
    "HIK_WEB_LOGIN_URL",
    "https://www.hik-connectru.com/views/login/index.html#/login",
).strip()
HIK_WEB_EMAIL = os.getenv("HIK_WEB_EMAIL", "").strip()
HIK_WEB_PASSWORD = os.getenv("HIK_WEB_PASSWORD", "").strip()
HIK_WEB_RECORDS_URL = os.getenv("HIK_WEB_RECORDS_URL", "").strip()
# Интерфейс hik-connectru доступен только на en/zh_CN/ar (см. language.json портала),
# поэтому шаги навигации по умолчанию английские. Русские варианты не совпадут
# никогда — раньше здесь стояли именно они.
HIK_WEB_NAV_STEPS = os.getenv(
    "HIK_WEB_NAV_STEPS",
    "Access Control|Search",
).strip()
# Внутреннее API портала (снято командой probe_hik_web). Браузер нужен только
# для получения cookies, сами данные тянутся обычным HTTP.
HIK_WEB_API_BASE = os.getenv("HIK_WEB_API_BASE", "https://team.hikcentralconnectru.com").strip()
HIK_WEB_API_RECORDS_PATH = os.getenv(
    "HIK_WEB_API_RECORDS_PATH",
    "/hcc/hccacs/v1/event/certificateRecords/search",
).strip()
HIK_WEB_API_PAGE_SIZE = _env_int("HIK_WEB_API_PAGE_SIZE", 100)
HIK_WEB_API_TIMEOUT = _env_int("HIK_WEB_API_TIMEOUT", 60)
# TTL кеша сессии портала: cookies живут дольше, но перелогин дешевле разбора ошибок.
HIK_WEB_SESSION_TTL = _env_int("HIK_WEB_SESSION_TTL", 6 * 60 * 60)

HIK_BROWSER_HEADLESS = _env_bool("HIK_BROWSER_HEADLESS", True)
HIK_BROWSER_TIMEOUT_MS = _env_int("HIK_BROWSER_TIMEOUT_MS", 120_000)
HIK_BROWSER_DOWNLOAD_DIR = os.getenv("HIK_BROWSER_DOWNLOAD_DIR", "/tmp/hik_exports").strip()

HIK_PROCESS_ENABLED = HIK_DATA_MODE != "off"

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

RATING_YEAR = {
    **RATING_YEAR,
    "CT_YEAR_BUDGET": _env_int("CT_YEAR_BUDGET", RATING_YEAR["CT_YEAR_BUDGET"]),
    "TOPIC_STALE_DAYS": _env_int("TOPIC_STALE_DAYS", RATING_YEAR["TOPIC_STALE_DAYS"]),
    "STALE_PENALTY_PER_TOPIC": -_env_int(
        "STALE_PENALTY_PER_TOPIC", abs(RATING_YEAR["STALE_PENALTY_PER_TOPIC"])
    ),
    "STALE_BLOCK_THRESHOLD": _env_int("STALE_BLOCK_THRESHOLD", RATING_YEAR["STALE_BLOCK_THRESHOLD"]),
}

# Переопределение штрафов/бонусов (положительные числа в .env → отрицательные штрафы в RATING_KP)
_rating_kp_overrides = {
    "LATE_LIGHT": -_env_int("LATE_PENALTY_LIGHT", abs(RATING_KP.get("LATE_LIGHT", -3))),
    "LATE_MODERATE": -_env_int("LATE_PENALTY_MODERATE", abs(RATING_KP.get("LATE_MODERATE", -5))),
    "LATE_SEVERE": -_env_int("LATE_PENALTY_SEVERE", abs(RATING_KP.get("LATE_SEVERE", -8))),
    "LATE_STREAK_7D": _env_int("LATE_STRIKE_7D_BONUS", RATING_KP.get("LATE_STREAK_7D", 5)),
    "LATE_STREAK_14D": _env_int("LATE_STRIKE_14D_BONUS", RATING_KP.get("LATE_STREAK_14D", 10)),
    "LATE_STREAK_21D": _env_int("LATE_STRIKE_21D_BONUS", RATING_KP.get("LATE_STREAK_21D", 15)),
    "ATTENDANCE_FULL_WEEK": _env_int("ATTENDANCE_FULL_WEEK_BONUS", RATING_KP.get("ATTENDANCE_FULL_WEEK", 15)),
    "ATTENDANCE_STREAK_7D": _env_int("ATTENDANCE_STRIKE_7D_BONUS", RATING_KP.get("ATTENDANCE_STREAK_7D", 5)),
}
RATING_KP = {**RATING_KP, **_rating_kp_overrides}

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
    # Задача recalculate_rating_daily удалена: она тянула данные через legacy
    # LXPClient по отдельному URL и конкурировала с настоящим пайплайном
    # (fetch_lxp_snapshot → recalculate_rating_for_date), который и остаётся
    # единственным источником рейтинга из LXP.
    "recalculate_pillars_weekly": {
        "task": "apps.progress.tasks.recalculate_pillars_weekly",
        "schedule": crontab(hour=22, minute=0, day_of_week="sun"),
    },
    "send_daily_quest": {
        "task": "apps.quests.tasks.send_daily_quest",
        "schedule": crontab(hour=7, minute=30),
    },
    "verify-auto-quests-evening": {
        "task": "apps.quests.tasks.verify_auto_quests",
        "schedule": crontab(hour=20, minute=15),
    },
    # Экземпляры квестов на сегодня — до первой проверки, чтобы студент видел
    # активные задания с утра.
    "create-period-quests": {
        "task": "apps.quests.tasks.create_period_quests",
        "schedule": crontab(hour=0, minute=5),
    },
    "verify-auto-quests-morning": {
        "task": "apps.quests.tasks.verify_auto_quests",
        "schedule": crontab(hour=6, minute=15),
    },
    "check_strikes_daily": {
        "task": "apps.progress.tasks.apply_strike_bonuses_daily",
        "schedule": crontab(hour=23, minute=30),
    },
    # Дуэли: без подведения итогов принятая дуэль висит вечно и блокирует
    # участникам новые вызовы.
    "resolve-duels-daily": {
        "task": "apps.social.tasks.resolve_duels",
        "schedule": crontab(hour=23, minute=45),
    },
    "pay-mentorship-weekly": {
        "task": "apps.social.tasks.pay_mentorship_weekly",
        "schedule": crontab(hour=20, minute=30, day_of_week="fri"),
    },
    "check_badges_weekly": {
        "task": "apps.badges.tasks.check_badges_weekly",
        "schedule": crontab(hour=21, minute=0, day_of_week="sun"),
    },
    # squad_digest_friday и curator_report_monday убраны из расписания:
    # их тела — заглушки, и запись в beat создавала видимость работающих
    # рассылок. Вернуть вместе с реализацией (см. apps/notifications/tasks.py).
    # Проходы забираются из портала раз в сутки за прошедший день.
    # Раньше здесь стояла ежечасная задача, которая в режиме browser поднимала
    # Playwright 24 раза в сутки и заново перекачивала весь день, а в 20:05/20:10
    # два экспорта шли одновременно и логинились в один аккаунт.
    # Портал допускает одну сессию на аккаунт, поэтому чем реже — тем лучше.
    "fetch-hik-web-daily": {
        "task": "apps.integrations.tasks.fetch_hik_web_daily",
        "schedule": crontab(hour=21, minute=0),
    },
    # Подбор событий, которые не удалось разобрать с первого раза
    # (например, у студента ещё не было отряда или расписания).
    "process-hik-events-daily": {
        "task": "apps.integrations.tasks.process_hik_events_daily",
        "schedule": crontab(hour=22, minute=30),
    },
    "process-late-events-hourly": {
        "task": "apps.integrations.tasks.process_late_events",
        "schedule": crontab(minute=30),
    },
    "monitor-health-and-alert": {
        "task": "apps.progress.tasks.monitor_health_and_alert",
        "schedule": crontab(minute="*/30"),
    },
}



