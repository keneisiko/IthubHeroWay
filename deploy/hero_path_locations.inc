# Общие location'ы для http- и https-сервера.

# Проверка здоровья самого nginx. Отдаётся им же, без обращения к бэкенду
# и до редиректа на https: проверка контейнера ходит по http на 127.0.0.1,
# и с включённым TLS она получала 301, шла за ним на https по адресу
# 127.0.0.1 и падала на несовпадении имени в сертификате. Контейнер при
# работающем сайте считался больным.
#
# Живость приложения проверяет сам контейнер web через /health/ — гасить
# прокси из-за поломки бэкенда не нужно: статику он отдаёт и без него.
location = /nginx-health {
    access_log off;
    add_header Content-Type text/plain always;
    return 200 "ok\n";
}

location /static/ {
    alias /var/www/static/;
    access_log off;
    # Файлы с хешем в имени (ManifestStaticFilesStorage) можно кешировать навсегда.
    expires 30d;
    add_header Cache-Control "public, immutable";
}

location /media/ {
    alias /var/www/media/;
    access_log off;
    expires 7d;
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
location ~ ^/(api|admin|swagger|schema|health|ready)/ {
    proxy_pass http://hero_path_web;
    include /etc/nginx/conf.d/hero_path_proxy.inc;
}

# Одностраничное приложение: любой неизвестный путь отдаём index.html, иначе
# перезагрузка страницы на /profile или /quests даёт 404 — маршрутизация
# живёт в браузере.
location / {
    root /usr/share/nginx/html;
    try_files $uri $uri/ /index.html;
}
