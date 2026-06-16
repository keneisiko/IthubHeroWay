from django.contrib import admin

from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq

from .models import Characteristic, CharacteristicHistory, RatingLog, UserStrike


@admin.register(RatingLog)
class RatingLogAdmin(ManagedRoleAdminMixin):
    list_display = ("user", "delta", "source", "reason", "created_at")
    list_filter = ("source", "created_at")
    search_fields = ("user__callsign", "user__username", "reason", "source_id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(Characteristic)
class CharacteristicAdmin(ManagedRoleAdminMixin):
    list_display = ("user", "pillar", "current", "peak", "last_updated")
    list_filter = ("pillar", "last_updated")
    search_fields = ("user__callsign", "user__username", "pillar")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(CharacteristicHistory)
class CharacteristicHistoryAdmin(ManagedRoleAdminMixin):
    list_display = ("characteristic", "value", "formula_version", "created_at")
    list_filter = ("formula_version", "created_at")
    search_fields = ("characteristic__user__callsign", "characteristic__pillar")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(UserStrike)
class UserStrikeAdmin(ManagedRoleAdminMixin):
    list_display = (
        "user",
        "attendance_strike",
        "late_strike",
        "last_attendance_date",
        "last_late_date",
        "updated_at",
    )
    search_fields = ("user__callsign", "user__username")
    readonly_fields = ("updated_at",)

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)
