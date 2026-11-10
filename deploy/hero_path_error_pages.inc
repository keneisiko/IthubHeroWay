error_page 400 401 403 404 405 413 429 500 502 503 504 /nginx-error.html;
error_page 497 =400 /nginx-error.html;

location = /nginx-error.html {
    internal;
    root /usr/share/nginx/html;
    add_header Cache-Control "no-store" always;
    include /etc/nginx/conf.d/hero_path_security_headers.inc;
}

location = /nginx-error-image.jpg {
    root /usr/share/nginx/html;
    expires 1d;
    include /etc/nginx/conf.d/hero_path_security_headers.inc;
}
