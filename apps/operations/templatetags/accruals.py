"""Состояние выключателя начислений для главной страницы админки."""

from __future__ import annotations

from django import template

from apps.operations.services.platform_settings import accruals_enabled, accruals_start_date

register = template.Library()


@register.simple_tag
def accruals_status() -> dict:
    return {"enabled": accruals_enabled(), "since": accruals_start_date()}
