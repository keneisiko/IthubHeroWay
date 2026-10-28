from django import forms
from django.contrib import admin, messages

from apps.integrations.services.lxp_group_import import slug
from apps.notifications.services.events import order_ready
from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq

from .models import COSMETIC_SLOTS, OrderStatus, Purchase, ShopItem, ShopItemSlot, ShopItemType
from .services import advance_orders


class ShopItemAdminForm(forms.ModelForm):
    class Meta:
        model = ShopItem
        fields = ("title", "description", "item_type", "slot", "price_coins", "stock", "is_active", "available_from", "available_to", "code")
        help_texts = {
            "item_type": "Косметика применяется сама. «Услугу» и «Прочее» (мерч) выдаёт сотрудник: "
            "покупка появится в разделе «Покупки».",
            "slot": "Обязателен для косметики (рамка, свечение, баннер) и буста (слот «Буст»).",
            "code": "Можно оставить пустым — соберётся из названия латиницей.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].required = False

    def clean(self):
        cleaned = super().clean()
        # Без слота косметику нельзя надеть, а буст не сработает: студент
        # заплатил бы за предмет, который ни на что не влияет.
        item_type, slot = cleaned.get("item_type"), cleaned.get("slot")
        if item_type == ShopItemType.COSMETIC and slot not in COSMETIC_SLOTS:
            self.add_error("slot", "Косметике нужен слот: рамка, свечение или баннер профиля.")
        if item_type == ShopItemType.BOOST and slot != ShopItemSlot.BOOST:
            self.add_error("slot", "Для буста выберите слот «Буст».")
        if not cleaned.get("code") and cleaned.get("title"):
            base = slug(cleaned["title"], "item")
            code, n = base, 2
            while ShopItem.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                code, n = f"{base}-{n}", n + 1
            cleaned["code"] = code
        return cleaned


@admin.register(ShopItem)
class ShopItemAdmin(ManagedRoleAdminMixin):
    form = ShopItemAdminForm
    list_display = ("title", "item_type", "slot", "price_coins", "stock", "is_active")
    list_editable = ("stock",)
    list_filter = ("item_type", "slot", "is_active")
    search_fields = ("code", "title", "description")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(Purchase)
class PurchaseAdmin(ManagedRoleAdminMixin):
    list_display = ("user", "item", "coins_spent", "status", "created_at", "issued_by")
    list_filter = ("status", "created_at", "item__item_type")
    readonly_fields = ("status", "status_changed_at", "issued_by")
    actions = ("mark_ready", "mark_issued")

    @admin.action(description="Готов к выдаче (студенту придёт уведомление)")
    def mark_ready(self, request, queryset):
        moved = advance_orders(queryset, OrderStatus.READY, request.user)
        for purchase in moved:
            order_ready(purchase)
        self._report(request, moved, queryset.count())

    @admin.action(description="Выдан")
    def mark_issued(self, request, queryset):
        moved = advance_orders(queryset, OrderStatus.ISSUED, request.user)
        self._report(request, moved, queryset.count())

    def _report(self, request, moved, selected: int) -> None:
        self.message_user(request, f"Статус изменён у {len(moved)} из {selected}.", messages.SUCCESS)
        if len(moved) < selected:
            self.message_user(
                request,
                "Остальные пропущены: косметика без выдачи или заказ уже дальше по статусу.",
                messages.WARNING,
            )
    search_fields = ("user__callsign", "user__username", "item__code", "item__title")
    autocomplete_fields = ("user", "item",)
    list_select_related = ("user", "item",)

    def has_add_permission(self, request):
        return False

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)
