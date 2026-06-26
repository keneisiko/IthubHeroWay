# HikCentral / Hik Connect

## Режимы (`HIK_DATA_MODE`)

| Режим | Когда использовать |
|-------|-------------------|
| **`browser`** | Нет OpenAPI — выгрузка XLSX через веб-портал [hik-connectru.com](https://www.hik-connectru.com) (Playwright, как LXP bot) |
| **`api`** | Есть `HIK_HOST` + `HIK_APP_KEY` + `HIK_APP_SECRET` (HikCentral OpenAPI) |
| **`snapshot`** | Ручной JSON/XLSX через `pull_hik_attendance` |
| **`off`** | Hik отключён |

Пайплайн одинаковый: **XLSX/API/JSON → `HikEvent` → `ExternalEvent` → штрафы / квесты**.

---

## Browser-режим (рекомендуется без API)

### `.env`

```env
HIK_DATA_MODE=browser
HIK_USE_BROWSER_EXPORT=1
HIK_WEB_LOGIN_URL=https://www.hik-connectru.com/views/login/index.html#/login
HIK_WEB_EMAIL=your@nalchik.ithub.ru
HIK_WEB_PASSWORD=***
HIK_WEB_NAV_STEPS=Контроль доступа|Записи прохода|Экспорт
HIK_BROWSER_HEADLESS=1
HIK_BROWSER_TIMEOUT_MS=120000
```

`HIK_WEB_NAV_STEPS` — тексты пунктов меню через `|`, по которым бот кликает после логина.  
Если знаете прямой URL страницы записей, задайте `HIK_WEB_RECORDS_URL` и упростите шаги.

### Ручной запуск

```bash
# Скачать XLSX за сегодня + импорт + штрафы
docker compose exec web python manage.py fetch_hik_browser_export

# За вчера (как nightly Celery)
docker compose exec web python manage.py fetch_hik_browser_export --yesterday

# Только скачать файл (отладка UI)
docker compose exec web python manage.py fetch_hik_browser_export --download-only --debug

# Импорт уже скачанного XLSX вручную
docker compose exec web python manage.py pull_hik_attendance --from-xlsx /path/export.xlsx --date 2026-05-30
```

### Celery

При `HIK_DATA_MODE=browser` задача `fetch_hik_events` (каждый час `:05`) вызывает browser-export за **сегодня**.

### Docker / Playwright

В `Dockerfile` установлен Chromium:

```bash
docker compose build web celery celery-beat
docker compose up -d
```

---

## OpenAPI-режим (`api`)

См. переменные `HIK_HOST`, `HIK_APP_KEY`, `HIK_APP_SECRET` в `.env.example`.

```bash
docker compose exec web python manage.py sync_hik_events
```

Подпись: `x-ca-key`, `x-ca-nonce`, `x-ca-timestamp`, `x-ca-signature`.

---

## Привязка студентов

В админке у пользователя:

- `hik_card_code` — номер карты из выгрузки (колонка «Номер карты» / `personCode`);
- `hik_person_id` — fallback.

Без карты событие сохранится в `HikEvent`, но не создаст `ExternalEvent`.

---

## Опоздания

`classify_entrance_against_schedule()` сравнивает время прохода с `Schedule` отряда (первая пара дня).

---

## Админка

- **HikEvent** — сырые события; сброс `processed` для повторной обработки.
- **HikSnapshot** — JSON-снимок (в т.ч. из XLSX).

---

## Отладка UI

```bash
docker compose exec web python manage.py fetch_hik_browser_export --debug
```

При ошибке сохраняется скриншот в `HIK_BROWSER_DOWNLOAD_DIR`.

Проверка логина (probe):

```bash
docker compose exec -e HIK_WEB_EMAIL=... -e HIK_WEB_PASSWORD=... web \
  python manage.py shell -c "from scripts.probe_hik_connect import main; main()"
```

Если меню в портале называется иначе — поправьте `HIK_WEB_NAV_STEPS` под ваш интерфейс.
