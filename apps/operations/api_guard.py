"""Ответ API на действие, которое до запуска платформы что-то начислило бы."""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from apps.operations.services.platform_settings import ACCRUALS_OFF_MESSAGE, accruals_enabled


def accruals_off_response() -> Response | None:
    """409 с понятным текстом, пока начисления выключены; иначе `None`.

    Отказ, а не молчаливый ноль: действие с нулевой наградой оставило бы
    запись (транзакцию квеста, респект, покупку), которая потом помешала бы
    получить настоящую награду или съела недельный лимит.
    """
    if accruals_enabled():
        return None
    return Response(
        {"detail": ACCRUALS_OFF_MESSAGE, "code": "accruals_disabled"},
        status=status.HTTP_409_CONFLICT,
    )
