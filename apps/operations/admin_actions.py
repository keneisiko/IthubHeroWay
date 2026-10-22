"""Действия админки с промежуточной страницей.

Встроенный способ Django — дополнительные поля в форме действий над
списком — в нашей теме выводится без подписей: сотрудник видел строку
пустых полей и не понимал, какое из них к какому действию относится.
Промежуточная страница показывает форму с подписями и подсказками и список
тех, кого действие коснётся, и только после «Подтвердить» что-то меняет.

Использование внутри действия::

    form, response = action_form(self, request, queryset, MyForm, title="...")
    if response is not None:
        return response
    ...  # работа с form.cleaned_data
"""

from __future__ import annotations

from django import forms
from django.contrib.admin import helpers
from django.template.response import TemplateResponse


def action_form(
    model_admin,
    request,
    queryset,
    form_class: type[forms.Form],
    *,
    title: str,
    intro: str = "",
    submit_label: str = "Подтвердить",
    skipped_note: str = "",
) -> tuple[forms.Form | None, TemplateResponse | None]:
    """Вернуть (заполненная форма, None) после подтверждения или (None, страница)."""
    if request.POST.get("apply"):
        form = form_class(request.POST)
        if form.is_valid():
            return form, None
    else:
        form = form_class()

    opts = model_admin.model._meta
    context = {
        **model_admin.admin_site.each_context(request),
        "title": title,
        "intro": intro,
        "submit_label": submit_label,
        "skipped_note": skipped_note,
        "form": form,
        "queryset": queryset,
        "action_name": request.POST.get("action", ""),
        "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
        "opts": opts,
        "cancel_url": request.get_full_path(),
    }
    return None, TemplateResponse(request, "admin/action_confirm.html", context)


def refuse_while_accruals_off(model_admin, request) -> bool:
    """Остановить действие, которое что-то начислило бы, пока начисления выключены.

    Разовая ручная выдача до запуска сломала бы «у всех ноль», а нашивка
    с ключом периода заблокировала бы будущее автоначисление. Возвращает
    True, если действие надо прервать (сообщение уже показано).
    """
    from django.contrib import messages

    from apps.operations.services.platform_settings import ACCRUALS_OFF_MESSAGE, accruals_enabled

    if accruals_enabled():
        return False
    model_admin.message_user(
        request,
        f"{ACCRUALS_OFF_MESSAGE} Включить их можно в «Настройки платформы».",
        level=messages.ERROR,
    )
    return True


class FrozenWhileAccrualsOffMixin:
    """Запретить создание и правку записей, несущих награду, пока начисления выключены.

    Запись «квест выполнен», серия, респект или дуэль, созданные руками до
    запуска, дали бы то, чего у студента «ещё нет». Ставить первым в bases.
    """

    def has_add_permission(self, request):
        from apps.operations.services.platform_settings import accruals_enabled

        return accruals_enabled() and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        from apps.operations.services.platform_settings import accruals_enabled

        return accruals_enabled() and super().has_change_permission(request, obj)
