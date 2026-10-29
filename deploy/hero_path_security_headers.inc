# Заголовки безопасности для одностраничного приложения.
#
# Подключаются в каждый location с собственным add_header: nginx не наследует
# add_header с уровня server, если в location объявлен хоть один свой —
# без повтора /assets/ и index.html остались бы без защиты.
#
# HSTS: браузер год ходит на сайт только по https.
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "same-origin" always;
# CSP только для фронта: свои скрипты, шрифты Google, картинки и аватары со
# своего домена. 'unsafe-inline' в стилях нужен React (style={...}) и
# встроенному <style> в index.html; скриптам он не разрешён.
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" always;
