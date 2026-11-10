# Общие location'ы для http- и https-сервера.

# Эндпоинт проверки контейнера объявлен в блоке 80 (deploy/nginx.conf):
# проверка ходит по http на 127.0.0.1, и этот include в блок 80 не
# подключается — там только подтверждение домена и редирект на https.

location ~* ^/(?:backups|[.]git|[.]env(?:[.][^/]*)?)(?:/|$) {
    error_page 404 =404 /download-placeholder.jpg;
    return 404;
}

location /static/ {
    alias /var/www/static/;
    access_log off;
    # Файлы с хешем в имени (ManifestStaticFilesStorage) можно кешировать навсегда.
    expires 30d;
    add_header Cache-Control "public, immutable";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
}

location ~* ^/media/(avatars/[^/]+\.(?:jpg|jpeg|png|gif|webp|avif|bmp|ico))$ {
    alias /var/www/media/$1;
    disable_symlinks on from=/var/www/media/;
    error_page 403 404 =404 /download-placeholder.jpg;
    access_log off;
    expires 7d;
    include /etc/nginx/conf.d/hero_path_security_headers.inc;
}

location = /media {
    error_page 404 =404 /download-placeholder.jpg;
    return 404;
}

location /media/ {
    error_page 404 =404 /download-placeholder.jpg;
    return 404;
}

location = /download-placeholder.jpg {
    internal;
    alias /usr/share/nginx/html/nginx-error-image.jpg;
    add_header Content-Disposition 'attachment; filename="download-placeholder.jpg"' always;
    add_header Cache-Control "private, no-store" always;
    include /etc/nginx/conf.d/hero_path_security_headers.inc;
}

# Прометей-метрики раскрывают внутреннее устройство и объём базы —
# наружу их отдавать не надо. django_prometheus вешает и /metrics, и /metrics/.
location ~ ^/metrics/?$ {
    if ($metrics_allowed = 0) {
        return 404;
    }
    proxy_pass http://hero_path_web;
    include /etc/nginx/conf.d/hero_path_proxy.inc;
}

# Всё, что обслуживает Django. Перечислены явно, потому что корень отдаёт
# одностраничное приложение.
# Документация и OpenAPI-схема закрыты на публичном сервере.
location ~ ^/(swagger|schema|redoc)(/|$) {
    return 404;
}

location ~ ^/(health|ready|live)(/|$) {
    return 404;
}

location ~ ^/(api|admin)/ {
    proxy_pass http://hero_path_web;
    include /etc/nginx/conf.d/hero_path_proxy.inc;
}

# Собранные бандлы Vite. Фоллбэк на index.html здесь выключен намеренно:
# иначе запрос удалённого после выката бандла получал «200 OK» с HTML внутри
# вместо JavaScript. Браузер такой ответ не выполняет и молча показывает
# белый экран — ошибки, по которой это видно, не возникает нигде.
# Имя файла содержит хеш содержимого, поэтому кеш вечный безопасен:
# меняется содержимое — меняется адрес.
location /assets/ {
    root /usr/share/nginx/html;
    try_files $uri =404;
    access_log off;
    expires 1y;
    add_header Cache-Control "public, immutable";
    include /etc/nginx/conf.d/hero_path_security_headers.inc;
}

# Одностраничное приложение: любой неизвестный путь отдаём index.html, иначе
# перезагрузка страницы на /profile или /quests даёт 404 — маршрутизация
# живёт в браузере.
location / {
    root /usr/share/nginx/html;
    try_files $uri $uri/ /index.html;
    include /etc/nginx/conf.d/hero_path_security_headers.inc;

    # index.html кешировать нельзя: в нём адреса бандлов, и студенты
    # остались бы на старой сборке до очистки кеша вручную. Браузер обязан
    # спросить сервер, а ETag сделает ответ пустым, когда ничего не менялось.
    location = /index.html {
        add_header Cache-Control "no-cache";
        include /etc/nginx/conf.d/hero_path_security_headers.inc;
    }
}
