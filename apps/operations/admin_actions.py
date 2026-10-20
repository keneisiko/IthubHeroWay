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
