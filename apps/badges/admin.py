from django import forms
from django.contrib import admin, messages
from django.db import transaction

from apps.integrations.services.lxp_group_import import slug
from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_hq
from apps.operations.services.cache import invalidate_rating_views
from apps.progress.services.rewards import grant_coins_with_daily_cap

from .metrics import FLAG_METRICS, MANUAL_CONDITION_KEY, METRIC_LABELS, THRESHOLD_METRICS
from .models import Badge, UserBadge

MAX_CONDITION_ROWS = 3


def _metric_choices():
    return [("", "— не задано —")] + [
        (key, METRIC_LABELS.get(key, key)) for key in (*THRESHOLD_METRICS, *FLAG_METRICS)
    ]


class BadgeAdminForm(forms.ModelForm):
    """Условие нашивки выбирается из списка, а не пишется в JSON.

    Раньше в поле «Условие» стояло `{}` без подсказок, и чтобы сделать
    нашивку «за рейтинг от 250», нужно было знать, что писать
    `{"rating_at_least": 250}`. Опечатка в ключе делала нашивку невыдаваемой
    без единой ошибки — в логе было лишь «неизвестные ключи условия».
    """

    award_mode = forms.ChoiceField(
        label="Как выдаётся",
        choices=(
            ("auto", "Автоматически, когда студент выполнит условие"),
            ("manual", "Вручную — выдаёт сотрудник"),
        ),
        initial="auto",
        help_text="Автоматическая проверка идёт по воскресеньям. Ручные нашивки выдаются "
        "в разделе «Нашивки студентов → Добавить».",
    )

    metric_1 = forms.ChoiceField(label="Условие 1", choices=_metric_choices, required=False)
    threshold_1 = forms.DecimalField(label="Порог 1", required=False, min_value=0, decimal_places=2)
    metric_2 = forms.ChoiceField(label="Условие 2", choices=_metric_choices, required=False)
    threshold_2 = forms.DecimalField(label="Порог 2", required=False, min_value=0, decimal_places=2)
    metric_3 = forms.ChoiceField(label="Условие 3", choices=_metric_choices, required=False)
    threshold_3 = forms.DecimalField(label="Порог 3", required=False, min_value=0, decimal_places=2)

    class Meta:
        model = Badge
        fields = ("title", "description", "category", "rarity", "reward_coins", "is_active", "code")
        help_texts = {
            "code": "Латиницей, без пробелов, например rating-250. Можно оставить пустым — "
            "соберётся из названия.",
            "reward_coins": "Сколько монет студент получит вместе с нашивкой.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].required = False
        self.fields["metric_1"].help_text = "Если условий несколько, нужно выполнить все сразу."

        condition = (self.instance.condition if self.instance and self.instance.pk else None) or {}
        if condition.get(MANUAL_CONDITION_KEY):
            self.initial["award_mode"] = "manual"
            return
        rows = [(k, v) for k, v in condition.items() if k != MANUAL_CONDITION_KEY]
        for i, (key, value) in enumerate(rows[:MAX_CONDITION_ROWS], start=1):
            self.initial[f"metric_{i}"] = key
            if key in THRESHOLD_METRICS:
                self.initial[f"threshold_{i}"] = value

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("code") and cleaned.get("title"):
            # Транслитом, а не slugify: тот выбрасывает кириллицу целиком.
            base = slug(cleaned["title"], "badge")
            code, n = base, 2
            while Badge.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                code, n = f"{base}-{n}", n + 1
            cleaned["code"] = code

        if cleaned.get("award_mode") == "manual":
            self._condition = {MANUAL_CONDITION_KEY: True}
            return cleaned

        condition: dict = {}
        for i in range(1, MAX_CONDITION_ROWS + 1):
            key = cleaned.get(f"metric_{i}")
            if not key:
                continue
            if key in FLAG_METRICS:
                condition[key] = True
                continue
            threshold = cleaned.get(f"threshold_{i}")
            if threshold is None:
                self.add_error(f"threshold_{i}", "Укажите число — с какого значения выдавать.")
                continue
            condition[key] = int(threshold) if threshold == int(threshold) else float(threshold)
        if not condition:
            raise forms.ValidationError(
                "Выберите хотя бы одно условие или переключите «Как выдаётся» на «Вручную»."
            )
        self._condition = condition
        return cleaned

    def save(self, commit=True):
        self.instance.condition = self._condition
        if not self.instance.code:
            self.instance.code = self.cleaned_data["code"]
        return super().save(commit)


@admin.register(Badge)
class BadgeAdmin(ManagedRoleAdminMixin):
    form = BadgeAdminForm
    list_display = ("title", "how_awarded", "category", "rarity", "reward_coins", "is_active")
    fieldsets = (
        (None, {"fields": ("title", "description", "category", "rarity", "reward_coins", "is_active", "code")}),
        (
            "Когда выдаётся",
            {
                "fields": (
                    "award_mode",
                    ("metric_1", "threshold_1"),
                    ("metric_2", "threshold_2"),
                    ("metric_3", "threshold_3"),
                )
            },
        ),
    )

    @admin.display(description="Когда выдаётся")
    def how_awarded(self, obj):
        condition = obj.condition or {}
        if condition.get(MANUAL_CONDITION_KEY):
            return "вручную"
        parts = []
        for key, value in condition.items():
            label = METRIC_LABELS.get(key, key).replace(", не меньше", "").replace(" (число не нужно)", "")
            parts.append(label if key in FLAG_METRICS else f"{label} ≥ {value}")
        return "; ".join(parts) or "—"
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
