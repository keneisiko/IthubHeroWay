# Hero Path IThub Backend

Backend for gamification platform "Path of Hero" built with Django + DRF.

## Stack

- Python 3.12
- Django + Django REST Framework + SimpleJWT
- PostgreSQL 16
- Redis 7 (cache/sessions + Celery broker)
- Celery worker + Celery beat
- drf-spectacular (OpenAPI/Swagger)
- django-prometheus
- sentry-sdk (optional)

## What you need

### Option A (recommended): Docker

- Docker Desktop (with Compose v2)

### Option B: Local Python run

- Python 3.12
- PostgreSQL (running)
- Redis (running)

## Environment variables

Create `.env` in project root:

```env
# DB
POSTGRES_DB=hero_path
POSTGRES_USER=hero_path
POSTGRES_PASSWORD=hero_path
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Redis / Celery
REDIS_URL=redis://redis:6379/0

# Integrations
TELEGRAM_BOT_TOKEN=replace_with_real_token
LXP_VERIFY_URL=
LXP_API_TOKEN=
YOUGILE_API_URL=
YOUGILE_API_TOKEN=

# Observability (optional)
SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=0.05
```

## Full run (Docker)

1) Build and run services:

```bash
docker compose up -d --build
```

2) Apply migrations:

```bash
docker compose exec web python manage.py migrate
```

3) (Optional) Create admin user:

```bash
docker compose exec web python manage.py createsuperuser
```

4) Run tests:

```bash
docker compose exec web python manage.py test apps.accounts.tests apps.social.tests apps.integrations.tests
```

## Full run (without Docker)

1) Create venv and install deps:

```bash
py -3 -m venv .venv
.venv\Scripts\activate
py -3 -m pip install -r requirements.txt
```

2) Set env vars for local services (example):

```bash
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5432
set REDIS_URL=redis://localhost:6379/0
set DJANGO_SETTINGS_MODULE=hero_path.settings.base
```

3) Run migrations and start server:

```bash
py -3 manage.py migrate
py -3 manage.py runserver 0.0.0.0:8000
```

## Verify that project is running

- API base: `http://localhost:8000/`
- Swagger UI: `http://localhost:8000/swagger/`
- OpenAPI schema: `http://localhost:8000/schema/`
- Health: `http://localhost:8000/health/`
- Readiness: `http://localhost:8000/ready/`
- Metrics: `http://localhost:8000/metrics/`
- Django admin: `http://localhost:8000/admin/`

Quick smoke:

```bash
curl http://localhost:8000/health/
curl http://localhost:8000/ready/
curl http://localhost:8000/metrics/
```

## API groups

- Auth: `/api/v1/auth/jwt/*`
- Profile/Dashboard: `/api/v1/profile/*`, `/api/v1/dashboard/`
- Squads: `/api/v1/squads/*`
- Quests: `/api/v1/quests/*`
- Shop: `/api/v1/shop/*`
- Badges: `/api/v1/badges/*`
- Rating/leaderboard: `/api/v1/rating/*`, `/api/v1/leaderboard/agents/`
- Social: `/api/v1/social/*`
- Integrations: `/api/v1/integrations/yougile/webhook/`

## Telegram bot

Run polling bot:

```bash
docker compose exec web python manage.py run_telegram_bot
```

Bot commands:

- `/activate` - account activation by study email + LXP password
- `/daily_quests` - show active daily quests
- `/profile` - show linked profile

