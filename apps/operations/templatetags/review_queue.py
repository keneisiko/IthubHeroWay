"""Тег для показа очереди подтверждений прямо на главной странице админки."""

from __future__ import annotations

from django import template

from apps.operations.services.review_queue import pending_proofs_count

register = template.Library()


@register.simple_tag
def pending_proofs_for(user) -> int:
    """Сколько заявок ждёт проверки именно у этого сотрудника.

    Без этого числа на главной куратор заходил в раздел проверок наугад:
    узнать, есть ли там что-то, можно было только открыв его.
    """
    if not getattr(user, "is_authenticated", False):
        return 0
    return pending_proofs_count(user)
