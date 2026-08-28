# Общие location'ы для http- и https-сервера.

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

location / {
    proxy_pass http://hero_path_web;
    include /etc/nginx/conf.d/hero_path_proxy.inc;
}
