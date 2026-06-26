# Аудит бэкенда «Путь героя IThub»

Дата: 2026-06-23  
Стек: Django + DRF + Celery + PostgreSQL + Redis (`docker-compose.yml`)

## Общий статус: **READY**

Критичные проверки инфраструктуры и API проходят. Внешние интеграции LXP/Hik в dev работают в режиме snapshot/off без prod credentials (⚠️).

---

## Сводка по 13 блокам чек-листа

| # | Блок | Статус | Комментарий |
|---|------|--------|-------------|
| 1 | Docker / инфра | ✅ | 6 контейнеров Up: web, frontend, db, redis, celery, celery-beat |
| 2 | Health / Ready / Metrics / Schema | ✅ | `/health/` status ok; `/ready/` ready; Prometheus `/metrics/`; OpenAPI `/schema/` |
| 3 | Auth, пользователи, миграции | ✅ | JWT + LXP login; миграции применены |
| 4 | LXP интеграция | ⚠️ | Cache key `lxp:gql:token`; snapshot/pull команды OK; prod token требует env |
| 5 | Hik интеграция | ⚠️ | `HIK_DATA_MODE=browser` (Playwright XLSX); `fetch_hik_browser_export`, `pull_hik_attendance --from-xlsx` |
| 6 | Celery | ✅ | 1 worker online; beat schedule 16 задач в `CELERY_BEAT_SCHEDULE` |
| 7 | API GET+POST | ✅ | Smoke: `scripts/audit_backend.sh` / `.ps1` |
| 8 | Анти-накрутка | ✅ | `RATING_LIMITS` подключены; тесты respect/self-report/coin cap/duel |
| 9 | Admin RBAC | ✅ | HQ deny на QuestRewardTransaction, SquadLeaderboardSnapshot, Schedule; curator scoping |
| 10 | Telegram алерты | ⚠️ | `test_alert`, dedup-тесты OK; live Telegram требует `TELEGRAM_*` |
| 11 | Dashboard feed | ✅ | `DashboardView.feed` из `QuestRewardTransaction` |
| 12 | Тесты | ✅ | 44 теста `apps.*` — OK после фиксов |
| 13 | Deliverables | ✅ | Этот отчёт + `scripts/audit_backend.*` |

---

## Инфраструктура (фаза 1)

**Docker compose ps (2026-06-23):**

| Сервис | Статус |
|--------|--------|
| web | Up :8000 |
| frontend | Up :5173 |
| db (postgres:16) | Up :5432 |
| redis:7 | Up :6379 |
| celery | Up |
| celery-beat | Up |

**HTTP smoke:**

```json
GET /health/  → {"status":"ok","healthy":true,"checks":{"db":true,"redis":true,"celery":true},...}
GET /ready/   → {"status":"ready","checks":{"db":true,"redis":true,"lxp":true},...}
GET /metrics/ → Prometheus text (200)
GET /schema/  → OpenAPI JSON (200)
```

> Спек чек-листа ожидал `{"status":"healthy"}` — фактически `status: ok` + поле `healthy: true` (alias добавлен).

---

## Спек vs факт (API paths и naming)

| Спек | Факт | Скрипт аудита |
|------|------|---------------|
| `{"status":"healthy"}` | `status: ok`, `healthy: true` | OK |
| `cache.get('lxp_access_token')` | `lxp:gql:token` | OK |
| `manage.py process_hik_events` | `sync_hik_events` + Celery `process_hik_events_daily` | OK |
| Hik без API | `fetch_hik_browser_export` (Playwright XLSX) | OK |
| `apply_strike_bonuses()` | `apply_strike_bonuses_daily` | OK |
| `User.rating` | `User.rating_current` | OK |
| `ExternalEvent.event_type='late'` | late в `payload`, filter `source='hik'` | OK |
| `POST /social/respect/` | `POST /social/respects/` | OK |
| `POST /badges/pin/` | `POST /badges/{code}/pin/` | OK |
| `POST /auth/jwt/create/` | + `POST /auth/login/` (LXP) | OK |

---

## Интеграции (фазы 3–5)

### LXP

| Проверка | Результат |
|----------|-----------|
| `import_lxp_students --help` | ✅ |
| `backfill_lxp_user_ids --help` | ✅ |
| `pull_lxp_performance --help` | ✅ |
| Cache token key | `lxp:gql:token` |
| Celery `fetch_lxp_snapshot` | В beat 01:45 |

### Hik

| Проверка | Результат |
|----------|-----------|
| `sync_hik_events --help` | ✅ |
| `pull_hik_attendance --help` | ✅ |
| `fetch_hik_browser_export --help` | ✅ |
| `backfill_hik_card_codes --help` | ✅ |
| `HIK_DATA_MODE` | snapshot (env HIK_* пустые в dev) |

### Celery

```
celery -A hero_path status → 1 node online
```

Beat: LXP 01:45/02:00, rating 06:00, quests 06:15/07:30/20:15, Hik hourly+daily, strikes 23:30, health alert */30.

---

## Исправления по итогам аудита

| Компонент | Проблема | Статус |
|-----------|----------|--------|
| `apps/social/views.py` | Hardcoded respect/duel limits | ✅ `RATING_LIMITS` |
| `apps/quests/views.py` | Hardcoded self-report 3/day | ✅ `MAX_DAILY_SELF_REPORTS` |
| `apps/progress/services/rewards.py` | Нет единого coin cap helper | ✅ `grant_coins_with_daily_cap` |
| `apps/quests/services/quest_completion.py` | Coin cap double-count в ledger | ✅ budget до insert |
| `apps/badges/services.py` | Badge coins без cap | ✅ cap через helper |
| `apps/accounts/admin.py` | Curator bonus без cap | ✅ cap через helper |
| `apps/quests/admin.py` | HQ видит reward ledger | ✅ HQ deny |
| `apps/schedule/admin.py` | Нет curator scoping | ✅ own squad / tutor 2–4 / HQ deny |
| `apps/accounts/views.py` | `feed: []` | ✅ `_dashboard_feed()` |
| `apps/operations/health_views.py` | Нет alias `healthy` | ✅ поле `healthy` |
| `apps/integrations/services/hik_attendance_processor.py` | `timezone.utc` (Django 5) | ✅ `datetime.timezone.utc` |

---

## Admin RBAC матрица (фаза 8)

| Модель | superuser/admin | curator | tutor | hq |
|--------|-----------------|---------|-------|-----|
| User | full | scoped | scoped | read dashboards |
| SelfReportProof | all | own squad | course 2–4 | **deny** |
| QuestRewardTransaction | full | view | view | **deny** |
| SquadLeaderboardSnapshot | full | view | view | **deny** |
| Schedule | full | own squad | course 2–4 | **deny** |

Mixin: `apps/operations/admin_rbac.ManagedRoleAdminMixin`

---

## Анти-накрутка — тесты

| Тест | Файл |
|------|------|
| Respect 1/week → 429 | `apps/social/tests.py` |
| Duel diff > 150 → 400 | `apps/social/tests.py` |
| Self-report 4/day → 429 | `apps/quests/tests_self_reports.py` |
| Coin cap 7×3 → max 20 | `apps/progress/tests_rewards.py` |
| HQ deny reward ledger | `apps/quests/tests_self_reports.py` |

Config: `hero_path/settings/rating_coefficients.py` → `RATING_LIMITS`

---

## Запуск аудита

```bash
# Linux/macOS
export API_BASE=http://localhost:8000
export API_LOGIN=user@nalchik.ithub.ru
export API_PASSWORD=...
./scripts/audit_backend.sh

# Windows
$env:API_BASE = "http://localhost:8000"
$env:API_LOGIN = "user@nalchik.ithub.ru"
$env:API_PASSWORD = "..."
.\scripts\audit_backend.ps1
```

Без `API_LOGIN`/`API_PASSWORD` скрипт проверяет infra + management commands; authenticated API — WARN.

JWT fallback: при неудаче LXP login скрипт пробует `POST /api/v1/auth/jwt/create/`.

---

## Верификация

```bash
docker compose exec web python manage.py test apps
./scripts/audit_backend.ps1   # или .sh
```

**Результат (2026-06-23):** 44/44 тестов OK; infra endpoints 200; Celery online.

---

## Известные ограничения (не блокеры)

1. **LXP login** в dev часто недоступен без prod credentials — фронт использует LXP; JWT/create для локальных Django users.
2. **Hik API** — без `HIK_HOST`/`HIK_APP_*` используется snapshot mode.
3. **Telegram** — live alerts требуют `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ADMIN_CHAT_ID`.
4. **Badge coin cap** — учитывает quest ledger; badge grants не пишут в `QuestRewardTransaction` (cap через общий budget helper).

См. также: [`docs/FRONTEND_AUDIT.md`](FRONTEND_AUDIT.md), [`scripts/audit_api.ps1`](../scripts/audit_api.ps1).
