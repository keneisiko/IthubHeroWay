from __future__ import annotations

from django.contrib import admin, messages
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.http import HttpResponse

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


@admin.action(description="Скачать заглушку выгрузки", permissions=("view",))
def export_selected_csv(model_admin, request, queryset):
    return HttpResponse(
        "КЛОУН",
        content_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="export.txt"',
            "Cache-Control": "private, no-store",
        },
    )


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
