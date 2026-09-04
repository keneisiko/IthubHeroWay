# Деплой «Пути героя»

Прод-стек: `docker-compose.prod.yml` — nginx, gunicorn, Celery worker, Celery beat,
Telegram-бот, PostgreSQL, Redis. **Фронтенд в стек не входит**: прод-сборка
`hero-path-front` пока не готова, там только dev-сервер Vite.

Все команды выполняются из корня проекта на сервере.

## 1. Что нужно на сервере

- Docker с Compose v2
- Домен, направленный A-записью на сервер
- Открытые наружу порты 80 и 443 (остальное — только внутренняя сеть Docker)
- ~4 ГБ RAM: образ тянет Chromium для Playwright (сбор данных из LXP и Hik)

## 2. Настройка окружения

```bash
cp .env.prod.example .env.prod
```

Заполнить обязательное:

| Переменная | Что будет, если не задать |
|---|---|
| `SECRET_KEY` | приложение не стартует (так и задумано) |
| `ALLOWED_HOSTS` | приложение не стартует |
| `POSTGRES_PASSWORD` | не стартует база |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | браузерный фронт не сможет ходить в API |
| `TELEGRAM_BOT_TOKEN` | бот не поднимется, **и никто не сможет активировать аккаунт**; не будет уведомлений о дуэлях, респектах и проверке подтверждений |
| `TELEGRAM_ADMIN_CHAT_ID` | не будет алертов об ошибках |
| `LXP_BOT_EMAIL` / `LXP_BOT_PASSWORD` | не соберётся успеваемость, рейтинг замрёт |
| `YOUGILE_WEBHOOK_SECRET` | вебхук YouGile будет отклонять все запросы (это безопасное поведение по умолчанию) |

Ключ генерируется так:

```bash
python -c "import secrets;print(secrets.token_urlsafe(64))"
```

> Пока нет TLS-сертификата, поставьте `SECURE_SSL_REDIRECT=0`. Иначе Django будет
> редиректить на https, которого ещё нет, и вы получите цикл редиректов.

## 3. Первый запуск

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Контейнер `web` сам применяет миграции и собирает статику при старте — отдельно
запускать `migrate` не нужно. Проверить, что всё поднялось:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
curl -i http://localhost/health/
curl -i http://localhost/ready/
```

`/health/` показывает доступность БД, Redis и Celery; `/ready/` дополнительно
проверяет LXP.

## 4. Наполнение

```bash
alias dcp='docker compose -f docker-compose.prod.yml --env-file .env.prod'

# Администратор
dcp exec web python manage.py createsuperuser

# Шаблоны квестов (без них автопроверка ничего не начислит).
# Ежедневные и еженедельные квесты заводятся экземплярами на период —
# команда сразу создаёт их на сегодня.
dcp exec web python manage.py sync_quest_templates

# Студенты из LXP
dcp exec web python manage.py import_lxp_students --email-domain nalchik.ithub.ru
dcp exec web python manage.py backfill_lxp_user_ids --email-domain nalchik.ithub.ru

# Проверка Telegram-алертов
dcp exec web python manage.py test_alert
```

### Важно про активацию аккаунтов

Импорт из LXP заводит карточки **неактивными**. Войти на платформу студент
сможет только после `/activate` в Telegram-боте: там он подтверждает учебную
почту и пароль от LXP, и в этот момент аккаунт открывается.

Иначе войти мог бы любой, у кого есть пароль от LXP, даже не зная о боте.

Если база импортировалась старой версией команды (до этого поведения) и все
аккаунты оказались активны — разово закройте вход тем, кто не привязал Telegram:

```bash
dcp exec web python manage.py deactivate_unlinked_agents --dry-run   # посмотреть
dcp exec web python manage.py deactivate_unlinked_agents             # применить
```

Команда не трогает кураторов, тьюторов, штаб и staff — они входят не через бота.

### Новый учебный год

Рейтинг копится за год, поэтому 1 сентября его нужно обнулить — иначе
четверокурсник соревнуется с первокурсником, имея фору за прошлые годы:

```bash
dcp exec web python manage.py start_rating_year --dry-run
dcp exec web python manage.py start_rating_year
```

Итог прошлого года сохраняется в журнале рейтинга. Подробности модели —
[docs/RATING_FROM_LXP.md](RATING_FROM_LXP.md).

## 5. TLS

Получить сертификат (nginx уже отдаёт `/.well-known/acme-challenge/` из
`deploy/certbot`):

```bash
docker run --rm \
  -v "$PWD/deploy/certbot:/var/www/certbot" \
  -v "$PWD/deploy/certs:/etc/letsencrypt" \
  certbot/certbot certonly --webroot -w /var/www/certbot -d hero.example.ru
```

Затем в [deploy/nginx.conf](../deploy/nginx.conf) раскомментировать server-блок
для 443 и редирект с 80, в `.env.prod` выставить `SECURE_SSL_REDIRECT=1` и
перезапустить nginx:

```bash
dcp restart nginx web
```

Сертификаты живут 90 дней — продление поставьте в cron хоста.

## 6. Обновление версии

```bash
git pull
dcp up -d --build
```

Миграции применятся при старте `web`. Если миграция долгая или несовместимая —
остановите `celery`/`celery-beat` перед выкатом, чтобы фоновые задачи не работали
с наполовину обновлённой схемой.

## 7. Бэкапы

```bash
sh scripts/backup_db.sh
```

Дампы кладутся в `./backups`, старше 14 дней удаляются (`KEEP_DAYS`). Поставьте
скрипт в cron хоста. Восстановление:

```bash
gunzip -c backups/hero_path_20260827_033000.sql.gz | \
  dcp exec -T db psql -U hero_path -d hero_path
```

Отдельно бэкапьте том `media` — там аватары студентов, в дамп базы они не входят.

## 8. Эксплуатация

**Логи:**

```bash
dcp logs -f web
dcp logs -f celery
dcp logs -f telegram-bot
```

**Метрики:** `/metrics/` закрыт nginx для всех, кроме приватных подсетей
(см. блок `geo $metrics_allowed` в [deploy/nginx.conf](../deploy/nginx.conf)).
Prometheus должен ходить из той же сети.

**Расписание Celery** (часовой пояс `Europe/Moscow`):

| Время | Задача |
|---|---|
| 01:45 | обновление токена LXP |
| 02:00 | снимок успеваемости LXP → пересчёт рейтинга |
| 00:05 | создание экземпляров квестов на день/неделю |
| 06:15 и 20:15 | автопроверка квестов |
| каждый час :05 | обработка проходов Hik |
| 20:10 | выгрузка проходов Hik за прошедший день |
| 23:30 | бонусы за серии |
| 23:45 | подведение итогов дуэлей, снятие протухших вызовов |
| пт 20:30 | монеты наставникам за подшефных |
| вс 21:00 / 22:00 | значки, пересчёт характеристик |

**Единственная реплика beat.** Второй экземпляр `celery-beat` продублирует всё
расписание — то есть удвоит начисления рейтинга.

## 9. Известные ограничения

- **Фронтенд не разворачивается этим стеком** — нужна прод-сборка (`npm run build`
  + отдача статики). Пока API доступен, UI — нет.
- **LXP и Hik в режиме `browser`** — это Playwright, ходящий по чужим порталам.
  Редизайн `newlxp.ru` или `hik-connectru.com` ломает сбор данных, а на нём
  висят рейтинг и квесты. Алерты в Telegram придут, но данные за день будут
  потеряны до ручного повтора команды.
- **Миграции запускаются из `web`** — при масштабировании до нескольких реплик
  вынесите их в отдельный разовый job.
- **Пулера соединений нет.** При росте числа воркеров считайте
  `GUNICORN_WORKERS × реплики + celery + beat + бот` против
  `POSTGRES_MAX_CONNECTIONS`, либо ставьте pgbouncer и `DB_CONN_MAX_AGE=0`.
