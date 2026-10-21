from __future__ import annotations

import csv

from django.contrib import admin, messages
from django.contrib.admin.utils import label_for_field, lookup_field
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import strip_tags

from apps.accounts.models import Role, User


def is_superadmin(user: User) -> bool:
    return bool(user and user.is_authenticated and user.is_superuser)


def is_admin(user: User) -> bool:
    return bool(user and user.is_authenticated and user.role == Role.ADMIN)


def is_curator(user: User) -> bool:
    return bool(user and user.is_authenticated and user.role == Role.CURATOR)


def is_tutor(user: User) -> bool:
    return bool(user and user.is_authenticated and user.role == Role.TUTOR)


def is_hq(user: User) -> bool:
    return bool(user and user.is_authenticated and user.role == Role.HQ)


def is_management(user: User) -> bool:
    return any((is_superadmin(user), is_admin(user), is_curator(user), is_tutor(user), is_hq(user)))


def _set_active(model_admin, request, queryset, value: bool) -> None:
    """Включить или выключить выбранные записи, записав это в историю."""
    changed = [obj for obj in queryset if obj.is_active != value]
    queryset.filter(pk__in=[obj.pk for obj in changed]).update(is_active=value)
    state = "включено" if value else "выключено"
    for obj in changed:
        model_admin.log_change(request, obj, f"Массово {state}")
    unchanged = queryset.count() - len(changed)
    tail = f" Уже были в этом состоянии: {unchanged}." if unchanged else ""
    model_admin.message_user(request, f"{state.capitalize()}: {len(changed)}.{tail}", messages.SUCCESS)


@admin.action(description="Выгрузить в Excel (CSV)")
def export_selected_csv(model_admin, request, queryset):
    """Выбранные строки — с теми же колонками, что видны в списке.

    Самое частое, о чём просит администрация: «пришли список». Раньше это
    означало обращение к разработчику. Файл открывается в Excel двойным
    щелчком: UTF-8 с BOM и точка с запятой как разделитель.
    """
    columns = [name for name in model_admin.get_list_display(request) if name != "action_checkbox"]
    opts = model_admin.model._meta
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    stamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M")
    response["Content-Disposition"] = f'attachment; filename="{opts.model_name}_{stamp}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow([strip_tags(str(label_for_field(name, model_admin.model, model_admin))) for name in columns])
    for obj in queryset:
        row = []
        for name in columns:
            try:
                _, _, value = lookup_field(name, obj, model_admin)
            except Exception:  # noqa: BLE001 — колонка, которую не посчитать, не должна ронять выгрузку
                value = ""
            if isinstance(value, bool):
                value = "да" if value else "нет"
            row.append(strip_tags(str(value if value is not None else "")))
        writer.writerow(row)
    return response


@admin.action(description="Сделать активными")
def activate_selected(model_admin, request, queryset):
    _set_active(model_admin, request, queryset, True)


@admin.action(description="Сделать неактивными")
def deactivate_selected(model_admin, request, queryset):
    _set_active(model_admin, request, queryset, False)


class ManagedRoleAdminMixin(admin.ModelAdmin):
    """Base permission gates for role-based admin panels."""

    # Включать и выключать записи пачкой: в списке квестов единственным
    # действием было «Удалить выбранные», и чтобы снять квест, его удаляли.
    # Даётся автоматически всем разделам, где у модели есть is_active.
    bulk_active_actions = True
    # Удаление, которое каскадом стирает историю (квест — прогресс студентов,
    # награды и заявки; нашивка — у всех, кто её получил). В таких разделах
    # удалять может только суперпользователь, остальным — «Сделать неактивными».
    deactivate_instead_of_delete = False

    def _has_active_flag(self) -> bool:
        try:
            field = self.model._meta.get_field("is_active")
        except Exception:  # noqa: BLE001 — поля нет
            return False
        return field.get_internal_type() == "BooleanField"

    def get_actions(self, request):
        actions = super().get_actions(request)
        if self.bulk_active_actions and self._has_active_flag() and self.has_change_permission(request):
            for func in (activate_selected, deactivate_selected):
                actions[func.__name__] = (func, func.__name__, func.short_description)
        if self.has_view_permission(request):
            actions["export_selected_csv"] = (
                export_selected_csv,
                "export_selected_csv",
                export_selected_csv.short_description,
            )
        return actions

    def has_module_permission(self, request):
        return is_management(request.user)

    def has_view_permission(self, request, obj=None):
        return is_management(request.user)

    def has_add_permission(self, request):
        return is_management(request.user)

    def has_change_permission(self, request, obj=None):
        return is_management(request.user)

    def has_delete_permission(self, request, obj=None):
        if self.deactivate_instead_of_delete:
            return is_superadmin(request.user)
        return is_superadmin(request.user) or is_admin(request.user)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Убрать «удалить» и «изменить» связанную запись из чужих форм.

        Рядом с полем «Отряд» в карточке студента стоял красный крестик —
        удаление самого отряда, а не отвязка студента. Новичок нажимал его,
        чтобы убрать студента из отряда. Связанные записи правятся в своих
        разделах; добавление и просмотр остаются.
        """
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        widget = getattr(formfield, "widget", None)
        if isinstance(widget, RelatedFieldWidgetWrapper):
            widget.can_delete_related = False
            widget.can_change_related = False
        return formfield
