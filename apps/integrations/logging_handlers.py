"""Ошибки из логов — в Telegram администратору.

Падение Celery-задачи уже приходило в чат (celery_signals), но большая часть
сбоев до него не доходит: код ловит исключение, пишет `logger.exception`
и идёт дальше. Например, проверка квеста у одного студента упала, задача
в целом завершилась успешно — и об этом знал только лог контейнера.

Обработчик подключён к логгеру приложений на уровне ERROR. Одинаковые ошибки
схлопываются: ключ — логгер, место в коде и шаблон сообщения (без подставленных
значений), так что сбой на 500 студентах даёт одно сообщение, а не 500.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import traceback

# Логгеры, чьи ошибки сюда не идут: сам канал алертов (иначе сбой отправки
# порождал бы новую отправку) и сигнал Celery, который шлёт алерт сам.
SKIP_LOGGERS = (
    "apps.integrations.services.telegram_alert",
    "apps.integrations.services.telegram_notify",
    "apps.integrations.celery_signals",
)

_local = threading.local()


class TelegramErrorHandler(logging.Handler):
    def __init__(self, level: int = logging.ERROR) -> None:
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(SKIP_LOGGERS) or getattr(record, "skip_telegram", False):
            return
        if getattr(_local, "busy", False):
            return
        _local.busy = True
        try:
            from apps.integrations.services.telegram_alert import send_alert_to_admin

            place = f"{record.pathname.rsplit('/apps/', 1)[-1]}:{record.lineno} ({record.funcName})"
            key = hashlib.sha1(f"{record.name}|{place}|{record.msg}".encode()).hexdigest()[:16]
            send_alert_to_admin(
                title=f"Ошибка: {record.name}",
                message=self._details(record, place),
                error_type="error",
                deduplicate_key=f"log:{key}",
                is_critical=record.levelno >= logging.CRITICAL,
            )
        except Exception:  # noqa: BLE001 — логирование не должно ронять код, который логирует
            pass
        finally:
            _local.busy = False

    @staticmethod
    def _details(record: logging.LogRecord, place: str) -> str:
        lines = [f"Где: {place}", f"Сообщение: {record.getMessage()}"]
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            tb = "".join(traceback.format_exception(*record.exc_info)).strip().splitlines()
            lines.append(f"Ошибка: {type(exc).__name__}: {exc}")
            lines.append("Трассировка (хвост):\n" + "\n".join(tb[-12:]))
        return "\n".join(lines)
