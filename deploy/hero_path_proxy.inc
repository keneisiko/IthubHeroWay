proxy_http_version 1.1;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
# Django доверяет этому заголовку (SECURE_PROXY_SSL_HEADER): за проксёй
# без него он считает соединение незашифрованным и редиректит в цикл.
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host  $host;
proxy_redirect off;
proxy_connect_timeout 10s;
proxy_read_timeout 70s;
