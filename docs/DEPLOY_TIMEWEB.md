# Развёртывание на Timeweb Cloud

Пошагово: от заказа сервера до работающего домена. Общая документация по
прод-стеку — [DEPLOY.md](DEPLOY.md); здесь только то, что специфично для
Timeweb, и порядок действий целиком.

Панель: <https://timeweb.cloud/my>, раздел **Облачные серверы**.

---

## 1. Заказ сервера

| Параметр | Значение | Почему так |
|---|---|---|
| Образ | Ubuntu 24.04 или 26.04 | скрипт подготовки рассчитан на Ubuntu |
| Регион | Санкт-Петербург (SPB-3) | ближайший по задержке |
| Конфигурация | 2 × 3.3 ГГц, **4 ГБ**, 50 ГБ NVMe | 1 000 ₽/мес |
| Публичный IPv4 | нужен | 200 ₽/мес, без него сервер недоступен снаружи |
| Бэкапы | включить | 300 ₽/мес |
| SSH-ключ | добавить свой | вход по паролю root — плохая идея |

Итого около **1 500 ₽/мес**. Оплата почасовая, списывается с баланса: при нуле
сервер сначала блокируется, затем удаляется вместе с диском. Держите на балансе
запас хотя бы на месяц вперёд.

> Тариф на 2 ГБ не берите: сборка фронта и установка Chromium для Playwright не
> помещаются в память, сборка падает с `killed` без объяснений.

## 2. Подготовка сервера

Подключиться (IP виден в карточке сервера):

```bash
ssh root@ВАШ_IP
```

Скрипт ставит Docker, добавляет swap, включает файрвол и переводит часы на
московское время — расписание Celery расписано именно в нём:

```bash
apt-get update && apt-get install -y git
git clone https://github.com/keneisiko/IthubHeroWay.git /opt/hero_path
cd /opt/hero_path
bash deploy/bootstrap_ubuntu.sh
```

Проверить:

```bash
docker run --rm hello-world
```

## 3. Домен

У колледжа есть `ithub-nalchik.ru`. Заведите поддомен, например
`hero.ithub-nalchik.ru`, **A-записью на IP сервера**. Запись должна
разойтись до выпуска сертификата, иначе Let's Encrypt откажет:

```bash
dig +short hero.ithub-nalchik.ru
```

Должен вернуться IP сервера.

## 4. Настройки

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

Минимум, без которого не стартует:

```
SECRET_KEY=<64 случайных символа>
ALLOWED_HOSTS=hero.ithub-nalchik.ru,127.0.0.1,localhost
CORS_ALLOWED_ORIGINS=https://hero.ithub-nalchik.ru
CSRF_TRUSTED_ORIGINS=https://hero.ithub-nalchik.ru
POSTGRES_PASSWORD=<длинный случайный>
SECURE_SSL_REDIRECT=0
COOKIE_SECURE=0
```

Ключ:

```bash
python3 -c "import secrets;print(secrets.token_urlsafe(64))"
```

`SECURE_SSL_REDIRECT=0` — временно: сертификата ещё нет, и с единицей вы
получите цикл редиректов на https. Вернём в 1 на шаге 6.

Дальше — интеграции: `TELEGRAM_BOT_TOKEN` (без него студенты не смогут
активировать аккаунт), `LXP_BOT_EMAIL` / `LXP_BOT_PASSWORD`,
`TELEGRAM_ADMIN_CHAT_ID`, `YOUGILE_WEBHOOK_SECRET`. Полная таблица — в
[DEPLOY.md](DEPLOY.md#2-настройка-окружения).

> `.env.prod` в репозиторий не попадает (`.gitignore`). Не копируйте его в
> общие чаты: там пароли от LXP и токен бота.

## 5. Первый запуск

```bash
cd /opt/hero_path
docker compose -p hero_prod -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Первая сборка идёт долго — минут десять: ставится Chromium и собирается фронт.
Миграции и статику контейнер `web` применяет сам.

```bash
alias dcp='docker compose -p hero_prod -f docker-compose.prod.yml --env-file .env.prod'
dcp ps
curl -i http://localhost/health/
```

## 6. Сертификат

```bash
docker run --rm \
  -v /opt/hero_path/deploy/certbot:/var/www/certbot \
  -v /opt/hero_path/deploy/certs:/etc/letsencrypt \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d hero.ithub-nalchik.ru --agree-tos -m college@ithub-nalchik.ru --no-eff-email
```

В [deploy/nginx.conf](../deploy/nginx.conf) блок 443 и редирект уже включены,
менять там нечего. В `.env.prod` верните боевые значения —
`SECURE_SSL_REDIRECT=1` и `COOKIE_SECURE=1`, — проверьте конфиг и перезапустите:

```bash
dcp exec nginx nginx -t
```

```bash
dcp restart nginx web
```

Продление сертификата — в cron хоста (`crontab -e`):

```
0 4 * * 1 docker run --rm -v /opt/hero_path/deploy/certbot:/var/www/certbot -v /opt/hero_path/deploy/certs:/etc/letsencrypt certbot/certbot renew --quiet && docker compose -p hero_prod -f /opt/hero_path/docker-compose.prod.yml --env-file /opt/hero_path/.env.prod restart nginx
```

## 7. Наполнение

```bash
dcp exec web python manage.py createsuperuser
dcp exec web python manage.py sync_quest_templates
# Каталоги магазина и нашивок: без этого разделы у студентов пустые.
dcp exec web python manage.py sync_catalogs
```

Проверить статусы тем LXP до первого начисления по Положению — если будущие
КТ попадут в расчёт как несданные, успеваемость обвалится всей группе:

```bash
dcp exec web python manage.py probe_topic_statuses
```

Импорт студентов. Для пилота — одна группа:

```bash
dcp exec web python manage.py import_lxp_group --list
dcp exec web python manage.py import_lxp_group --group-id <ID> --squad-code itr2-24 --squad-name "3ИТР2.9.24" --course 3
```

Весь колледж:

```bash
dcp exec web python manage.py import_lxp_students --email-domain nalchik.ithub.ru
dcp exec web python manage.py backfill_lxp_user_ids --email-domain nalchik.ithub.ru
```

Карточки создаются закрытыми: вход открывается после `/activate` в
Telegram-боте. Это защита от входа по одному лишь паролю от LXP.

## 8. Бэкапы

Бэкапы Timeweb — это снимок диска целиком, он не заменяет дамп базы: из снимка
нельзя достать одну таблицу. Поставьте дамп в cron хоста:

```
30 3 * * * cd /opt/hero_path && sh scripts/backup_db.sh >> /var/log/hero_path_backup.log 2>&1
```

Перенаправление в журнал обязательно. Без него молчит и успех, и провал:
скрипт полгода падал с `service "db" is not running`, потому что не передавал
`-p hero_prod`, и дампов не было вовсе — а в cron это выглядело как тишина.

Проверьте, что дампы действительно появляются:

```bash
ls -lh /opt/hero_path/backups | tail -5
```

Дампы кладутся в `./backups`, старше 14 дней удаляются. Том `media` (аватары)
бэкапится отдельно — в дамп базы он не входит.

## 9. Обновление

```bash
cd /opt/hero_path && git pull && dcp up -d --build
```

---

## Что проверить после установки

| Проверка | Ожидаемо |
|---|---|
| `curl -i https://hero.ithub-nalchik.ru/health/` | 200, база и Redis доступны |
| `/admin/` открывается, вход работает | да |
| `dcp logs telegram-bot` | бот запустился, а не падает по кругу |
| `dcp exec web python manage.py test_alert` | сообщение пришло в Telegram |
| `dcp logs celery-beat` | расписание загружено |

## Если что-то не так

**Контейнер `web` перезапускается.** Почти всегда — незаполненный `SECRET_KEY`
или `ALLOWED_HOSTS`: профиль `prod` намеренно падает на старте, а не работает
с dev-ключом. Смотрите `dcp logs web`.

**`telegram-bot` в цикле перезапусков.** Не задан `TELEGRAM_BOT_TOKEN`.
Остальная платформа при этом работает, но студенты не смогут активироваться.

**Цикл редиректов в браузере.** `SECURE_SSL_REDIRECT=1` без сертификата.

**403 «Ошибка проверки CSRF» при входе в админку по http.** Куки помечены
`Secure` и по незашифрованному соединению браузером не сохраняются. До выпуска
сертификата поставьте `COOKIE_SECURE=0`, после — обязательно верните `1`.

**`nginx` стал `unhealthy` после включения TLS, а сайт при этом работает.**
Проверка контейнера ходила на `http://127.0.0.1/health/`, получала редирект
на https, шла за ним по адресу `127.0.0.1` и падала на несовпадении имени
в сертификате. Теперь nginx проверяет сам себя через `/nginx-health`,
который отдаёт он же, до редиректа и без обращения к бэкенду. Если контейнер
собран со старым compose-файлом — обновите его.

Перед перезапуском конфиг стоит проверить изнутри контейнера, иначе опечатка
уронит сайт:

```bash
dcp exec nginx nginx -t
```

**`web` стал `unhealthy` сразу после включения TLS.** Проверка контейнера
ходит в gunicorn напрямую по http, а с `SECURE_SSL_REDIRECT=1` Django отвечает
на такой запрос редиректом. Проверка шлёт `X-Forwarded-Proto: https`, как это
делает nginx; если контейнер собран со старым compose-файлом — обновите его.

**`web` поднялся, но `unhealthy`, а nginx и Celery не стартовали.** В
`ALLOWED_HOSTS` нет `127.0.0.1` и `localhost`: healthcheck ходит на
`http://127.0.0.1:8000/health/` и получает 400 `DisallowedHost`. Добавьте оба
адреса и повторите `up -d`.

**Сборка падает с `killed`.** Не хватило памяти — проверьте, что swap подключён:
`swapon --show`.

**Порт 5432 недоступен снаружи.** Так и задумано: база наружу не публикуется.
Подключаться — через `dcp exec db psql -U hero_path`.
