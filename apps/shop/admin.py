from django import forms
from django.contrib import admin

from apps.integrations.services.lxp_group_import import slug
from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq

from .models import COSMETIC_SLOTS, Purchase, ShopItem, ShopItemSlot, ShopItemType


class ShopItemAdminForm(forms.ModelForm):
    class Meta:
        model = ShopItem
        fields = ("title", "description", "item_type", "slot", "price_coins", "is_active", "available_from", "available_to", "code")
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
    list_display = ("title", "item_type", "slot", "price_coins", "is_active")
    list_filter = ("item_type", "slot", "is_active")
    search_fields = ("code", "title", "description")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)


@admin.register(Purchase)
class PurchaseAdmin(ManagedRoleAdminMixin):
    list_display = ("user", "item", "coins_spent", "created_at")
    list_filter = ("created_at", "item__item_type")
    search_fields = ("user__callsign", "user__username", "item__code", "item__title")
    autocomplete_fields = ("user", "item",)
    list_select_related = ("user", "item",)

    def has_add_permission(self, request):
        return False

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)
