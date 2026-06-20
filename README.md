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

Скопируйте [.env.example](.env.example) в `.env` и заполните значения. В продакшене секреты передавайте из хранилища (Vault, CI secrets, переменные платформы), не коммитьте `.env`.

Ключевые группы: PostgreSQL, Redis, Telegram, LXP (GraphQL и опционально браузерный токен), HikCentral (`HIK_*`), YouGile, Sentry.

## Telegram-алерты об ошибках

Централизованный сервис: [`apps/integrations/services/telegram_alert.py`](apps/integrations/services/telegram_alert.py).

- **Переменные:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT_ID`, `TELEGRAM_ALERTS_ENABLED=1`, `TELEGRAM_ALERT_DEDUP_TTL=3600`, `ENVIRONMENT_NAME=production`
- **Что шлётся:** падения Celery (`task_failure`), ошибки LXP auth, Hik API, Django 500 (middleware), рейтинг (`IntegrityError`), health-monitor каждые 30 мин
- **Дедупликация:** одинаковые некритичные алерты — не чаще 1 раза в час; critical — всегда
- **Тест:**

```bash
docker compose exec web python manage.py test_alert
```

## LXP: операции (Celery, алерты, рейтинг)

- **Расписание** (`CELERY_BEAT_SCHEDULE`, часовой пояс проекта — `TIME_ZONE`): задача `refresh-lxp-token` в **01:45**, снимок `fetch-lxp-snapshot` в **02:00**. Перед сбором снимка токен дополнительно обновляется синхронно внутри задачи.
- **Связь с LXP**: у пользователя поле `lxp_user_id` (проставляется при `import_lxp_students` или `backfill_lxp_user_ids`).
- **Рейтинг из снимка**: после сохранения `LXPSnapshot` вызывается `recalculate_rating_for_date` (маппинг и коэффициенты — [docs/RATING_FROM_LXP.md](docs/RATING_FROM_LXP.md)).
- **Каталог запросов GraphQL**: [docs/LXP_GRAPHQL_CATALOG.md](docs/LXP_GRAPHQL_CATALOG.md).
- **Проверка Telegram-алерта админу:**

```bash
docker compose exec web python manage.py test_alert
```

**Backfill `lxp_user_id`** для уже импортированных пользователей:

```bash
docker compose exec web python manage.py backfill_lxp_user_ids --email-domain nalchik.ithub.ru
```

## HikCentral: проходы (турникеты)

- Документация: [docs/HIKCENTRAL.md](docs/HIKCENTRAL.md).
- В админке у пользователя задайте **`hik_card_code`** (совпадает с `personCode` / номер карты из Hik).
- Celery Beat: **`fetch-hik-events-hourly`** (каждый час с `:05`) и **`process-hik-events-daily`** (`process_hik_events_daily` — догрузка большой очереди в 20:00; основная обработка также вызывается из `fetch_hik_events`).
- Ручной запуск выгрузки:

```bash
docker compose exec web python manage.py sync_hik_events
```

События с маппингом сохраняются в **`ExternalEvent`** (`source=hik`). Учёт опозданий от расписания и автоприменение штрафов рейтинга к опоре «Ритм» — отдельный этап.

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
docker compose exec web python manage.py test apps.accounts.tests apps.social.tests apps.integrations apps.progress
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

Super user
```bash
docker compose exec web python manage.py createsuperuser
```

ученики только Нальчик
```bash
docker compose exec web python manage.py import_lxp_students --email-domain nalchik.ithub.ru
```

сброс пользователей (кроме staff/superuser) и повторный импорт Нальчика
```bash
docker compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); U.objects.filter(is_superuser=False,is_staff=False).delete(); print('deleted')"
docker compose exec web python manage.py import_lxp_students --email-domain nalchik.ithub.ru
```

тг бот
```bash
docker compose exec web python manage.py run_telegram_bot
```

### Успеваемость в БД (LXP → `LXPSnapshot` + пользователи)

1. Импорт учеников и `lxp_user_id`:
```bash
docker compose exec web python manage.py import_lxp_students --email-domain nalchik.ithub.ru
docker compose exec web python manage.py backfill_lxp_user_ids --email-domain nalchik.ithub.ru
```

2. При необходимости токен бота браузера (если включён `LXP_USE_BROWSER_TOKEN_BOT`):
```bash
docker compose exec web python manage.py fetch_lxp_browser_token --debug
```

3. Снять успеваемость и записать JSON в базу (`LXPSnapshot`), затем применить к рейтингу у тех, у кого **активирован Telegram**:

```bash
docker compose exec web python manage.py pull_lxp_performance
```

Для **стейджа без реальных активаций Telegram** можно один раз добавить синтетические привязки агентам с `lxp_user_id`:
```bash
docker compose exec web python manage.py pull_lxp_performance --synthetic-telegram-agents
```

Только сохранить снимок без `RatingLog` / рейтинга: `--skip-rating`. Как по расписанию Celery (вчера): `--yesterday`.

LXP токен вручную + старый вызов через shell
```bash
docker compose exec web python manage.py fetch_lxp_browser_token --debug
docker compose exec web python manage.py shell -c "from apps.integrations.tasks import fetch_lxp_snapshot; print(fetch_lxp_snapshot())"
docker compose exec web python manage.py shell -c "from apps.integrations.models import LXPSnapshot; s=LXPSnapshot.objects.order_by('-date').first(); print(s.date if s else None); print((s.data or {}).get('meta') if s else None)"
```

посмотреть успеваемость из последнего snapshot (sample)
```bash
docker compose exec web python manage.py shell -c "from apps.integrations.models import LXPSnapshot; import json; s=LXPSnapshot.objects.order_by('-date').first(); d=s.data if s else {}; print((d.get('meta') if d else None)); grades=d.get('grades',{}).get('data',{}); print('grades_count', len(grades)); print('grades_sample', json.dumps(dict(list(grades.items())[:3]), ensure_ascii=False))"
```