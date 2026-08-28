proxy_http_version 1.1;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
# По этому заголовку Django понимает схему запроса. На белом IP без TLS здесь
# будет http — и это важно: с https в профиле white_ip Django начал бы
# требовать защищённые куки, которые браузер по http не отправляет.
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host  $host;
proxy_redirect off;
proxy_connect_timeout 10s;
proxy_read_timeout 70s;
