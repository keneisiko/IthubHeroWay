"""Профиль для запуска на белом IP без домена и без TLS.

Отличие от `prod` — только в требованиях к HTTPS. Профиль `prod` включает
SECURE_SSL_REDIRECT, HSTS и защищённые куки: по адресу вида http://203.0.113.10
это гарантированный отказ, причём молчаливый. Браузер не отправляет
`Secure`-куку по http, поэтому вход в админку выглядит так: логин и пароль
верные, страница перезагружается — и снова форма входа, без единой ошибки
в логах. Плюс редирект на https, которого нет, даёт бесконечный цикл.

Всё остальное — обязательный SECRET_KEY, ALLOWED_HOSTS, заголовки
безопасности, логирование — наследуется от `prod` без изменений.

Профиль осознанно менее защищён, чем `prod`: трафик идёт открытым текстом,
включая пароли от LXP на входе. Это допустимо для демонстрации и тестового
стенда. Как только появится домен, переходите на `prod` с сертификатом —
см. docs/DEPLOY.md.
"""

import os

from .base import _env_bool
from .prod import *  # noqa: F401,F403

# Без TLS редиректить некуда: с включённым редиректом любой запрос уходил бы
# на https://<ip>, где никто не слушает.
SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", False)

# Главная причина, по которой prod-профиль не работает по http.
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", False)

# HSTS по http бессмыслен, а при случайном включении браузер запомнит
# требование https для этого адреса на месяц вперёд — и починить это
# на стороне сервера уже нельзя.
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False


def _origins_from_hosts(hosts: list[str], extra: str) -> list[str]:
    """Собрать список origin'ов из ALLOWED_HOSTS.

    На белом IP адрес известен только в момент запуска, а Django требует
    origin со схемой. Перечислять руками и в ALLOWED_HOSTS, и в
    CSRF_TRUSTED_ORIGINS — верный способ забыть одно из двух и получить
    «CSRF verification failed» при входе в админку.
    """
    origins = [item.strip() for item in (extra or "").split(",") if item.strip()]
    scheme = "https" if SECURE_SSL_REDIRECT else "http"
    for host in hosts:
        if host in {"*", ""}:
            continue
        candidate = f"{scheme}://{host}"
        if candidate not in origins:
            origins.append(candidate)
    return origins


CSRF_TRUSTED_ORIGINS = _origins_from_hosts(ALLOWED_HOSTS, os.getenv("CSRF_TRUSTED_ORIGINS", ""))

# Фронт и API живут на одном origin за nginx, поэтому CORS в норме не нужен.
# Список остаётся настраиваемым: пригодится, если фронт запускают отдельно.
CORS_ALLOWED_ORIGINS = _origins_from_hosts(
    ALLOWED_HOSTS, os.getenv("CORS_ALLOWED_ORIGINS", "")
)
