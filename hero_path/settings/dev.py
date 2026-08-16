"""Настройки для локальной разработки.

Небезопасные значения допустимы только здесь: DEBUG, широкий ALLOWED_HOSTS,
дефолтный SECRET_KEY. Для продакшена см. hero_path/settings/prod.py.
"""

from .base import *  # noqa: F401,F403
from .base import _env_bool, _env_list

DEBUG = _env_bool("DEBUG", True)

ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", ["localhost", "127.0.0.1", "0.0.0.0", "web"])
