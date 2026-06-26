FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN playwright install --with-deps chromium

COPY . /app/

EXPOSE 8000

CMD ["gunicorn", "hero_path.wsgi:application", "-b", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]

