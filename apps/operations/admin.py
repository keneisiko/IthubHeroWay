"""Экран «Настройки платформы»."""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_admin, is_superadmin
from apps.operations.models import PlatformSettings
from apps.operations.services.platform_settings import default_values


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(ManagedRoleAdminMixin):
    """Одна страница, без списка.

    Менять могут только администраторы: от этих чисел зависят монеты всех
    студентов сразу. Куратор и тьютор видят значения, но не правят. Каждое
    изменение пишется в историю объекта в виде «было → стало».
    """

    fieldsets = (
        ("Монеты и квесты", {"fields": ("max_daily_coins", "max_daily_self_reports")}),
        (
            "Отряды и соцмеханики",
            {
                "fields": (
                    "squad_weekly_bonus_percent",
                    "squad_weekly_bonus_coins",
                    "respect_weekly_limit",
                    "duel_bet",
                    "duel_duration_days",
                    "duel_invite_ttl_days",
                    "duel_max_rating_diff",
                )
            },
        ),
        (
            "Посещаемость и успеваемость",
            {
                "fields": (
                    "hik_late_grace_minutes",
                    "ct_scope",
                    "ct_min_actual",
                    "require_telegram_link_for_scoring",
                )
            },
        ),
        (
            "Тарифы Положения — только просмотр",
            {
                "fields": ("polozhenie_reference",),
                "description": (
                    "Тарифы меняются только новой редакцией Положения, через "
                    "разработчика: смена посреди недели дала бы части студентов "
                    "начисление по старому тарифу, части — по новому."
                ),
            },
        ),
        ("Служебное", {"fields": ("updated_at",)}),
    )
    readonly_fields = ("polozhenie_reference", "updated_at")

    # --- одна строка вместо списка -------------------------------------------

    def changelist_view(self, request, extra_context=None):
        obj = self._get_or_create()
        url = reverse(
            f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk]
        )
        return HttpResponseRedirect(url)

    def _get_or_create(self) -> PlatformSettings:
        obj = PlatformSettings.objects.filter(pk=PlatformSettings.SINGLETON_PK).first()
        if obj is None:
            obj = PlatformSettings(**default_values())
            obj.save()
        return obj

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return is_superadmin(request.user) or is_admin(request.user)

    # --- журнал «было → стало» -----------------------------------------------

    def construct_change_message(self, request, form, formsets, add=False):
        """Стандартная история пишет только имена полей.

        «Изменено: Дневной предел монет» не отвечает на вопрос, с чего вдруг
        студенты стали получать меньше. Пишем старое и новое значение.
        """
        if add or not form.changed_data:
            return super().construct_change_message(request, form, formsets, add)
        parts = []
        for name in form.changed_data:
            field = form.fields[name]
            before = form.initial.get(name)
            after = form.cleaned_data.get(name)
            parts.append(f"{field.label}: {_display(field, before)} → {_display(field, after)}")
        return "; ".join(parts)

    # --- справка по тарифам ----------------------------------------------------

    @admin.display(description="Действующие тарифы")
    def polozhenie_reference(self, obj):
        from apps.progress.services.polozhenie_awards import tariff_choices

        academic = getattr(settings, "POLOZHENIE_ACADEMIC", {})
        statuses = getattr(settings, "POLOZHENIE_STATUSES", ())
        penalties = getattr(settings, "POLOZHENIE_PENALTIES", {})
        header = format_html(
            "<p><b>Редакция {} от {}.</b> Недельный максимум: КТ — {}, посещаемость — {}. "
            "Списание за пропуск: {} за пару, не больше {} за день.</p>",
            getattr(settings, "POLOZHENIE_VERSION", "—"),
            getattr(settings, "POLOZHENIE_DATE", "—"),
            academic.get("CT_WEEKLY_MAX", "—"),
            academic.get("ATTENDANCE_WEEKLY_MAX", "—"),
            penalties.get("ABSENCE_PER_LESSON", "—"),
            penalties.get("ABSENCE_DAILY_MAX", "—"),
        )
        status_line = format_html(
            "<p><b>Статусы:</b> {}</p>",
            format_html_join(", ", "{} — от {}", ((title, threshold) for threshold, _, title in statuses)),
        )
        tariffs = format_html(
            "<p><b>Мероприятия, олимпиады, проекты</b> (рейтинг / монеты):</p><ul>{}</ul>",
            format_html_join("", "<li>{}</li>", ((label,) for _, label in tariff_choices())),
        )
        return format_html("{}{}{}", header, status_line, tariffs)


def _display(field, value) -> str:
    choices = dict(getattr(field, "choices", ()) or ())
    if value in choices:
        return str(choices[value])
    if isinstance(value, bool):
        return "да" if value else "нет"
    return "—" if value in (None, "") else str(value)
