from django.contrib import admin

from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq

from .models import Duel, Mentorship, Respect


@admin.register(Respect)
class RespectAdmin(ManagedRoleAdminMixin):
    list_display = ("from_user", "to_user", "message", "created_at")
    list_filter = ("created_at",)
    search_fields = ("from_user__callsign", "to_user__callsign", "message")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(Duel)
class DuelAdmin(ManagedRoleAdminMixin):
    list_display = ("challenger", "opponent", "status", "created_at", "resolved_at")
    list_filter = ("status", "created_at")
    search_fields = ("challenger__callsign", "opponent__callsign")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(Mentorship)
class MentorshipAdmin(ManagedRoleAdminMixin):
    list_display = ("mentor", "mentee", "started_at", "ended_at")
    list_filter = ("started_at", "ended_at")
    search_fields = ("mentor__callsign", "mentee__callsign")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)
