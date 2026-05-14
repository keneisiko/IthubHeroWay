# HikCentral (Hik-Connect OpenAPI)

## Назначение

- Celery (`fetch_hik_events`) периодически выгружает события доступа и кладёт их в `HikEvent`.
- Для пользователей с заполненным `User.hik_card_code` (или совпадением `hik_person_id` с `personId` в событии) создаётся `ExternalEvent` с `source=hik` и полезной нагрузкой прохода.
- Расчёт **опозданий относительно расписания пар** и автоматическое списание рейтинга по опорам — **следующий этап** (нужны слоты расписания и согласованные поля из Hik).

## Настройка

См. переменные в [`.env.example`](../.env.example) и `hero_path/settings/base.py`.

Важно:

- Подпись запроса: `x-ca-key`, `x-ca-nonce`, `x-ca-timestamp`, `x-ca-signature` (HMAC-SHA256 + Base64). При 401 сравните строку подписи с документацией вашей сборки HCP; при необходимости переключите `HIK_SIGNATURE_DASH_HEADERS` или заголовок `HIK_SIGNATURE_HEADERS`.
- Путь API `HIK_ARTEMIS_EVENT_RECORDS_PATH` и поля тела (`startTime` / `endTime`, имена полей пагинации) **зависят от версии платформы** — при ошибке 400 скорректируйте по официальному OpenAPI.
- Для тестов с самоподписанным TLS: `HIK_SSL_VERIFY=0` (только не в проде без понимания рисков).

## Ручной запуск

```bash
docker compose exec web python manage.py sync_hik_events
```

## Админка

- У студента: поля `hik_card_code`, `hik_person_id`.
- Раздел `HikEvent`: просмотр сырых событий, сброс `processed` для повторной обработки.
