"""Фабрики типовых объектов для тестов.

Тесты проекта написаны на unittest (`manage.py test`), а не на pytest, поэтому
здесь лежат обычные функции-хелперы, а не фикстуры. Файл называется
`conftest.py` по договорённости команды — как единая точка входа за тестовыми
данными; каждый тестовый модуль иначе заново собирает пользователя, привязку
Telegram, отряд и квест, и эти сборки успели разойтись между собой.
"""

from __future__ import annotations

import itertools

from django.contrib.auth import get_user_model

_counter = itertools.count(1)


def unique_suffix() -> int:
    """Сквозной счётчик, чтобы уникальные поля не конфликтовали между вызовами."""
    return next(_counter)


def make_squad(**kwargs):
    from apps.accounts.models import Squad

    n = unique_suffix()
    params = {"code": f"squad-{n}", "name": f"Отряд {n}"}
    params.update(kwargs)
    return Squad.objects.create(**params)


def make_agent(*, telegram: bool = False, password: str = "x", **kwargs):
    """Создать агента; `telegram=True` добавляет активную привязку Telegram.

    Привязка нужна почти всем тестам интеграций: без неё бот и алерты просто
    молча пропускают пользователя, и тест зеленеет, ничего не проверив.
    """
    from apps.accounts.models import Role

    User = get_user_model()
    n = unique_suffix()
    params = {
        "username": f"agent{n}",
        "email": f"agent{n}@nalchik.ithub.ru",
        "callsign": f"agent_call_{n}",
        "role": Role.AGENT,
    }
    params.update(kwargs)
    user = User.objects.create_user(password=password, **params)
    if telegram:
        make_telegram_link(user)
    return user


def make_telegram_link(user, **kwargs):
    from apps.integrations.models import TelegramAccountLink

    n = unique_suffix()
    params = {
        "telegram_user_id": 700_000 + n,
        "telegram_chat_id": 700_000 + n,
        "telegram_username": f"tg{n}",
        "is_active": True,
    }
    params.update(kwargs)
    return TelegramAccountLink.objects.create(user=user, **params)


def make_quest(**kwargs):
    from apps.quests.models import Quest

    n = unique_suffix()
    params = {
        "code": f"quest-{n}",
        "title": f"Квест {n}",
        "reward_coins": 10,
        "reward_rating_delta": 5,
        "is_active": True,
    }
    params.update(kwargs)
    return Quest.objects.create(**params)
