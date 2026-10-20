from django.contrib import admin, messages
from django.db import transaction

from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq
from apps.operations.services.cache import invalidate_rating_views
from apps.progress.services.rewards import grant_coins_with_daily_cap

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
    """Выдача нашивки вручную.

    Добавление было запрещено с первого коммита админки, хотя часть нашивок
    иначе выдать нельзя: «Стажировка» и «Выпуск» платформа сама узнать не
    может, и руководство персонала описывало именно этот экран. Кнопки
    «Добавить» при этом не было.
    """

    list_display = ("user", "badge", "source", "is_pinned", "acquired_at")
    list_filter = ("is_pinned", "acquired_at", "badge__category", "source")
    search_fields = ("user__callsign", "user__username", "badge__code", "badge__title")
    list_select_related = ("user", "badge",)
    autocomplete_fields = ("user", "badge")

    def save_model(self, request, obj, form, change):
        """Выдать нашивку и начислить монеты за неё — как это делает автомат.

        Иначе выданная руками нашивка отличалась бы от полученной по правилу:
        та же награда, но без монет.
        """
        if change:
            super().save_model(request, obj, form, change)
            return

        obj.source = obj.source or f"manual:{request.user.username}"
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if obj.badge.reward_coins:
                granted = grant_coins_with_daily_cap(obj.user, obj.badge.reward_coins)
                if granted < obj.badge.reward_coins:
                    # Дневной предел монет — не ошибка, но знать о нём нужно:
                    # иначе выдача выглядит как полная, а монет пришло меньше.
                    self.message_user(
                        request,
                        f"Начислено {granted} из {obj.badge.reward_coins} монет: "
                        "упёрлись в дневной предел.",
                        level=messages.WARNING,
                    )
        invalidate_rating_views(obj.user.username)

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)
