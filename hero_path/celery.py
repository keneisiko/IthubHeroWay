import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hero_path.settings.base")

app = Celery("hero_path")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

import apps.integrations.celery_signals  # noqa: E402, F401 — task_failure alerts


@app.task
def ping() -> str:
    return "pong"

