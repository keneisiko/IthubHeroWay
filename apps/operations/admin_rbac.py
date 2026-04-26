from __future__ import annotations

from django.contrib import admin

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


class ManagedRoleAdminMixin(admin.ModelAdmin):
    """Base permission gates for role-based admin panels."""

    def has_module_permission(self, request):
        return is_management(request.user)

    def has_view_permission(self, request, obj=None):
        return is_management(request.user)

    def has_add_permission(self, request):
        return is_management(request.user)

    def has_change_permission(self, request, obj=None):
        return is_management(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_superadmin(request.user) or is_admin(request.user)
