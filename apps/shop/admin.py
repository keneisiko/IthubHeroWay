from django.contrib import admin

from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq

from .models import Purchase, ShopItem


@admin.register(ShopItem)
class ShopItemAdmin(ManagedRoleAdminMixin):
    list_display = ("code", "title", "item_type", "price_coins", "is_active")
    list_filter = ("item_type", "is_active")
    search_fields = ("code", "title", "description")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(Purchase)
class PurchaseAdmin(ManagedRoleAdminMixin):
    list_display = ("user", "item", "coins_spent", "created_at")
    list_filter = ("created_at", "item__item_type")
    search_fields = ("user__callsign", "user__username", "item__code", "item__title")

    def has_add_permission(self, request):
        return False

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)
