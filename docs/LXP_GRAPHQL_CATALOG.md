# LXP GraphQL — документация для команды

## Канонический каталог запросов

Рабочий набор проверенных запросов и сценариев хранится в пакете документации проекта (папка «Для Заракуша» на рабочем столе / внутренний git с отчётами). В репозитории backend — только ссылка и операционные заметки.

## Продакшен API

| Параметр | Значение (типично) |
|----------|---------------------|
| GraphQL endpoint | `LXP_GRAPHQL_ENDPOINT`, по умолчанию `https://api.newlxp.ru/graphql` |
| Web / логин | `LXP_WEB_LOGIN_URL`, `LXP_WEB_BASE_URL` |
| Продукт | newlxp (LXP) |

**Владелец API / контакт при смене схемы:** `TBD` (указать ФИО и канал связи).

## Код в этом репозитории

- Клиент: `apps/integrations/services/lxp_graphql_client.py`
- Снимок и Beat: `apps/integrations/tasks.py`, расписание `hero_path/settings/base.py` → `CELERY_BEAT_SCHEDULE`
- Импорт и `lxp_user_id`: `apps/integrations/management/commands/import_lxp_students.py`, `backfill_lxp_user_ids.py`

При изменении типов GraphQL (`GetLearningGroupsInput!` и т.д.) правки в первую очередь в клиенте и в каноническом каталоге запросов.
