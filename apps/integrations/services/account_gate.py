"""Гейт входа на платформу.

Карточку студента заводит импорт из LXP, но подтверждением личности служит
привязка Telegram: пароль от LXP знает и сам студент, и он же — единственный
фактор на нашем логине. Поэтому импортированный аккаунт закрыт, пока человек
не прошёл /activate в боте.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model

from apps.accounts.models import Role


def deactivate_unlinked_agents() -> int:
    """Закрыть вход агентам без активной привязки Telegram.

    Нужен разово для баз, импортированных до того, как импорт стал создавать
    аккаунты неактивными. Штаб, кураторов, тьюторов и staff не трогаем:
    они входят не через бота.
    """
    User = get_user_model()
    qs = User.objects.filter(
        role=Role.AGENT,
        is_active=True,
        is_staff=False,
        is_superuser=False,
    ).exclude(telegram_link__is_active=True)
    return qs.update(is_active=False)
