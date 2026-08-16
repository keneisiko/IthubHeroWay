FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

WORKDIR /app

# Зависимости ставятся до копирования кода: слой с pip и Chromium (тяжёлый)
# не пересобирается при каждом изменении исходников.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && playwright install --with-deps chromium

# Непривилегированный пользователь. Каталог браузеров нужен ему на чтение,
# каталог выгрузок Hik — на запись.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /tmp/hik_exports \
    && chown -R app:app /tmp/hik_exports /app \
    && chmod -R a+rX /opt/playwright

COPY --chown=app:app . /app/

USER app

EXPOSE 8000

CMD ["gunicorn", "hero_path.wsgi:application", "-b", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
