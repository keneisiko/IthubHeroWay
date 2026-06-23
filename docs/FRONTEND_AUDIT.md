# Аудит фронтенда «Путь героя IThub»

Дата: 2026-06-23  
Стек: React 19 + Vite (`hero-path-front/`), Django DRF (`/api/v1/`)

## Сводка

| Область | До аудита | После критичных фиксов |
|---------|-----------|------------------------|
| Dashboard | частично | OK (кроме feed на backend) |
| Profile | много пробелов | OK (кроме «Карты пути») |
| Leaderboard | частично | OK |
| Squads | частично | OK (кроме блока топ-10 на странице) |
| Shop | частично | OK (кроме «Применить») |
| Quests | в основном OK | без изменений |
| Badges page | отсутствует | без изменений (только профиль) |

---

## Чек-лист по страницам

### 1. Dashboard (`/dashboard`)

| Блок | API | Статус | Комментарий |
|------|-----|--------|-------------|
| Рейтинг | `GET /dashboard/` | OK | 0–1000, count-up |
| Прогресс-бар зоны | `GET /dashboard/` | OK | `rating_progress` |
| Пятиугольник | `GET /dashboard/` | OK | `skills` / `skills_peak` |
| Активный квест | `GET /dashboard/` | OK | Пустое: «На сегодня всё. Отдыхай.» |
| Серия (Strike) | `GET /dashboard/` | OK | `strike.late_strike` |
| Лента активности | `GET /dashboard/` | FAIL (backend) | API всегда `feed: []` |
| Загрузка | — | OK | Спиннер при первой загрузке |
| Навигация | Sidebar | OK | 6 пунктов |

### 2. Profile (`/profile`, `/profile/:username`)

| Блок | API | Статус | Комментарий |
|------|-----|--------|-------------|
| Шапка (свой) | `GET /profile/me/` | OK | |
| Скрытие рейтинга (чужой) | `GET /profile/{username}/` | OK | «Скрыт» при `rating_current: null` |
| Скрытие цифр radar (чужой) | — | OK | Числа и tooltip скрыты |
| Карта пути | — | FAIL | Placeholder «в разработке» |
| Нашивки | `GET /badges/my/` | OK | Фильтр по категориям, 3 pinned сверху |
| Pin | `POST /badges/{code}/pin/` | OK | |
| Респект | `POST /social/respects/` | OK | На чужом профиле |
| Дуэль | `POST /social/duels/` | OK | Disabled если разница > 150 |
| Наставничество | `POST /social/mentorships/` | OK | |
| 404 профиль | — | OK | «Профиль не найден» |

### 3. Leaderboard (`/leaderboard`)

| Блок | API | Статус | Комментарий |
|------|-----|--------|-------------|
| Вкладки Агенты/Отряды | — | OK | |
| Топ агентов | `GET /leaderboard/agents/?page=1&page_size=20` | OK | |
| Фильтр по треку | `&track=dev-backend` | OK | Селект треков |
| Поиск | `&search=` | OK | Server-side (backend + frontend) |
| Моё место | `GET /rating/me/` | OK | Поле `rank` |
| Топ отрядов | `GET /squads/leaderboard/` | PARTIAL | Нет delta в API; кнопка «Отряд» disabled |

### 4. Squads (`/squads`)

| Блок | API | Статус | Комментарий |
|------|-----|--------|-------------|
| Мой отряд + бонус | `GET /squads/me/` | OK | |
| Участники + рейтинг | `GET /squads/{code}/members/?ordering=rating` | OK | |
| Поиск участников | `&search=` | OK | Server-side |
| Рейтинг отрядов (топ-10) | `GET /squads/leaderboard/` | FAIL | Блок не на странице |
| Пустое состояние | — | OK | «В отряде пока только вы» |

### 5. Shop (`/shop`)

| Блок | API | Статус | Комментарий |
|------|-----|--------|-------------|
| Баланс, категории, покупка | OK | OK | |
| Куплено → disabled | `GET /shop/my-purchases/` | OK | Кнопка «Куплено» |
| «Применить» кастомизацию | — | FAIL | Не реализовано |
| Изображения | — | PARTIAL | Fallback `palmSky` |

### 6. Quests (`/quests`)

| Блок | API | Статус |
|------|-----|--------|
| Вкладки, active/complete/history | OK | OK |
| auto_verify → без confirm | OK | OK |
| Самоотчёт, complete | OK | OK |
| Strike из dashboard | OK | OK |
| Стили личный/командный | FAIL | Нет отдельных стилей |
| Пагинация истории | FAIL | Весь список сразу |

### 7. Badges (`/badges`)

| Блок | Статус |
|------|--------|
| Отдельная страница | FAIL — нет маршрута |
| Функционал в профиле | OK |

### Глобальные состояния

| Проверка | Статус |
|----------|--------|
| 401 → `/login` | OK |
| 403 toast | OK | `api.ts` + react-hot-toast |
| 404 профиль | OK | |
| 500 toast | OK | |
| Skeleton loaders | FAIL | Везде spinner |

---

## Список проблем (оставшиеся)

| # | Страница | Блок | Проблема | Рекомендация |
|---|----------|------|----------|--------------|
| 1 | Dashboard | Лента | Backend отдаёт пустой `feed` | Заполнить `DashboardView` событиями из quest/reward log |
| 2 | Profile | Карта пути | Placeholder | Отдельный API + UI timeline |
| 3 | Squads | Топ отрядов | Нет блока на странице | Добавить секцию с `GET /squads/leaderboard/` |
| 4 | Shop | Применить | Нет apply | Endpoint + UI для cosmetic items |
| 5 | Quests | Стили | Нет personal/team CSS | Добавить классы по `quest_type` |
| 6 | Quests | История | Нет пагинации | `page`/`page_size` на фронте |
| 7 | Badges | `/badges` | Нет страницы | Новый route + tabs Мои/Все |
| 8 | Leaderboard | Отряды | Нет delta, кнопка disabled | Расширить API + navigate `/squads` |
| 9 | UI | Skeleton | Spinner вместо skeleton | CSS skeleton по макету |

---

## Матрица API: спек vs факт

| Спек | Факт (backend) | Фронт |
|------|----------------|-------|
| `POST /badges/pin/` | `POST /badges/{code}/pin/` | Использует fact |
| `POST /social/respect/` | `POST /social/respects/` | Использует fact |
| `POST /social/duel/create/` | `POST /social/duels/` | Использует fact |
| `POST /social/mentorship/take/` | `POST /social/mentorships/` | OK |
| `GET /rating/me/` + rank | `rank` добавлен | OK |
| `leaderboard/agents?search=` | Поддерживается | OK |

---

## Внесённые исправления (критичные)

### Frontend
- `hero-path-front/src/api.ts` — toast 403/500
- `hero-path-front/src/pages/Profile.tsx` — рейтинг, radar, pin, respect, duel, 404
- `hero-path-front/src/pages/Leaderboard.tsx` — track, page, search, rank из API
- `hero-path-front/src/pages/Squads.tsx` — rating участников, API search/ordering
- `hero-path-front/src/pages/Shop.tsx` — disabled для купленных
- `hero-path-front/src/pages/Dashboard.tsx` — loading, empty quest

### Backend
- `apps/progress/views.py` — `rank` в `/rating/me/`, `search` в leaderboard agents

### Scripts
- `scripts/audit_api.sh` — bash smoke-test
- `scripts/audit_api.ps1` — PowerShell smoke-test

---

## Проверка

```bash
# Frontend build
docker compose exec frontend npm run build

# Backend tests
docker compose exec web python manage.py test apps.progress apps.accounts.tests_squads_api

# API smoke (нужны рабочие credentials LXP)
$env:API_LOGIN="your@email"; $env:API_PASSWORD="***"
.\scripts\audit_api.ps1
```

Runtime smoke (Django test client, 2026-06-23): все ключевые GET endpoint → **200**.

---

## Навигация

Маршруты в `App.tsx`: `/dashboard`, `/profile`, `/profile/:username`, `/leaderboard`, `/quests`, `/shop`, `/squads`, `/login`. Sidebar — 6 пунктов.
