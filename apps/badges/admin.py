from django.contrib import admin

from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq

from .models import Badge, UserBadge


@admin.register(Badge)
class BadgeAdmin(ManagedRoleAdminMixin):
    list_display = ("code", "title", "category", "rarity", "reward_coins", "is_active")
    list_filter = ("category", "rarity", "is_active")
    search_fields = ("code", "title", "description")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(UserBadge)
class UserBadgeAdmin(ManagedRoleAdminMixin):
    list_display = ("user", "badge", "is_pinned", "acquired_at")
    list_filter = ("is_pinned", "acquired_at", "badge__category")
    search_fields = ("user__callsign", "user__username", "badge__code", "badge__title")

    def has_add_permission(self, request):
        return False

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)
