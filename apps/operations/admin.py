"""Экран «Настройки платформы»."""

from __future__ import annotations

import logging
from io import StringIO

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from apps.accounts.models import Role, User
from apps.badges.models import AvatarFrame, Badge
from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_admin, is_superadmin
from apps.operations.models import PlatformSettings
from apps.operations.services.platform_settings import default_values, switch_accruals

logger = logging.getLogger(__name__)

# Слово, которое надо вписать руками: случайный клик не обнулит всех студентов.
RESET_CONFIRM_WORD = "ОБНУЛИТЬ"


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(ManagedRoleAdminMixin):
    """Одна страница, без списка.

    Менять могут только администраторы: от этих чисел зависят монеты всех
    студентов сразу. Куратор и тьютор видят значения, но не правят. Каждое
    изменение пишется в историю объекта в виде «было → стало».
    """

    fieldsets = (
        (
            "Начисления",
            {
                "fields": ("accruals_panel", "reset_panel"),
                "description": (
                    "До запуска платформа заморожена: рейтинг, монеты, квесты, нашивки, "
                    "дуэли и респекты ничего не начисляют."
                ),
            },
        ),
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
    readonly_fields = ("accruals_panel", "reset_panel", "polozhenie_reference", "updated_at")

    # --- выключатель начислений ----------------------------------------------

    def get_urls(self):
        custom = [
            path(
                "accruals/",
                self.admin_site.admin_view(self.accruals_view),
                name="operations_platformsettings_accruals",
            ),
            path(
                "reset/",
                self.admin_site.admin_view(self.reset_view),
                name="operations_platformsettings_reset",
            ),
        ]
        return custom + super().get_urls()

    @admin.display(description="Состояние")
    def accruals_panel(self, obj):
        """Крупный статус и кнопка: включить без неё можно только осознанно."""
        url = reverse("admin:operations_platformsettings_accruals")
        since = obj.accruals_started_on.strftime("%d.%m.%Y") if obj.accruals_started_on else "—"
        if obj.accruals_enabled:
            status = format_html(
                '<span style="font-size:1.4em;font-weight:700;color:#1a7f37">Начисления включены</span>'
                " — сезон идёт с {}.",
                since,
            )
            label, css = "Остановить начисления", "btn btn-danger"
        else:
            last = format_html(" Последний период шёл с {}.", since) if obj.accruals_started_on else ""
            status = format_html(
                '<span style="font-size:1.4em;font-weight:700;color:#b42318">Начисления выключены</span>'
                " — ничего не начисляется.{}",
                last,
            )
            label, css = "Включить начисления", "btn btn-success"
        return format_html('{}<br><a class="{}" style="margin-top:8px" href="{}">{}</a>', status, css, url, label)

    def accruals_view(self, request):
        """Страница подтверждения: GET показывает последствия, POST переключает."""
        if not self.has_change_permission(request):
            raise PermissionDenied
        obj = self._get_or_create()
        turning_on = not obj.accruals_enabled
        change_url = reverse(
            f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk]
        )

        if request.method == "POST" and request.POST.get("apply"):
            # Страница подтверждения знает, КУДА переключает; применяем только если
            # состояние ещё такое же. Иначе двойной клик включил бы и сразу выключил.
            wanted = request.POST.get("target")
            if wanted not in ("on", "off") or (wanted == "on") != turning_on:
                self.message_user(
                    request,
                    "Начисления уже включены." if obj.accruals_enabled else "Начисления уже выключены.",
                    level=messages.WARNING,
                )
                return HttpResponseRedirect(change_url)
            before = obj.accruals_enabled
            updated = switch_accruals(turning_on)
            note = f"Начисления: {_display(None, before)} → {_display(None, updated.accruals_enabled)}"
            if turning_on:
                note += f"; сезон стартует с {updated.accruals_started_on:%d.%m.%Y}"
            self.log_change(request, updated, note)
            if turning_on:
                try:
                    self._spawn_period_quests()
                except Exception:
                    # Переключение уже сохранено; квесты создадутся ночной задачей.
                    logger.exception("Не удалось завести квесты при включении начислений")
                    self.message_user(
                        request,
                        "Начисления включены, но квесты на сегодня завести не удалось: "
                        "они появятся при ближайшей проверке.",
                        level=messages.WARNING,
                    )
            self.message_user(
                request,
                "Начисления включены. Сезон стартует с сегодняшнего дня."
                if turning_on
                else "Начисления остановлены.",
                level=messages.SUCCESS,
            )
            return HttpResponseRedirect(change_url)

        context = {
            **self.admin_site.each_context(request),
            "title": "Включить начисления" if turning_on else "Остановить начисления",
            "opts": obj._meta,
            "turning_on": turning_on,
            "target": "on" if turning_on else "off",
            "today": timezone.localdate(),
            "started_on": obj.accruals_started_on,
            "cancel_url": change_url,
        }
        return TemplateResponse(request, "admin/operations/accruals_switch.html", context)

    # --- обнуление студентов ------------------------------------------------

    @admin.display(description="Обнуление")
    def reset_panel(self, obj):
        """Кнопка видна всем, но работает только у суперадмина и при выключенных начислениях."""
        if obj.accruals_enabled:
            return "Обнулить данные студентов можно только при выключенных начислениях."
        url = reverse("admin:operations_platformsettings_reset")
        return format_html(
            '<a class="btn btn-outline-danger" href="{}">Обнулить данные студентов</a>', url
        )

    def reset_view(self, request):
        """Тот же reset_all_progress, что и с сервера, но кнопкой.

        Только суперадмин, только при выключенных начислениях и только после
        ввода слова-подтверждения. Нашивки с рамкой разработчика сохраняются.
        """
        if not is_superadmin(request.user):
            raise PermissionDenied
        obj = self._get_or_create()
        change_url = reverse(
            f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk]
        )
        if obj.accruals_enabled:
            self.message_user(
                request, "Сначала остановите начисления.", level=messages.ERROR
            )
            return HttpResponseRedirect(change_url)

        students = User.objects.filter(role=Role.AGENT).count()
        keep = list(
            Badge.objects.filter(avatar_frame=AvatarFrame.DEVELOPER).values_list("code", flat=True)
        )
        if request.method == "POST":
            if request.POST.get("confirm", "").strip().upper() != RESET_CONFIRM_WORD:
                self.message_user(
                    request,
                    f"Не обнулено: нужно вписать слово {RESET_CONFIRM_WORD}.",
                    level=messages.ERROR,
                )
                return HttpResponseRedirect(request.path)
            out = StringIO()
            try:
                call_command(
                    "reset_all_progress",
                    apply=True,
                    confirm="RESET",
                    expect_students=int(request.POST.get("students", -1)),
                    keep_badge=keep,
                    stdout=out,
                )
            except (CommandError, ValueError) as exc:
                self.message_user(request, f"Не обнулено: {exc}", level=messages.ERROR)
                return HttpResponseRedirect(change_url)
            logger.warning("Обнуление студентов из админки: %s\n%s",request.user, out.getvalue())
            self.log_change(request, obj, f"Обнулены данные студентов ({students})")
            self.message_user(
                request, f"Данные {students} студентов обнулены.", level=messages.SUCCESS
            )
            return HttpResponseRedirect(change_url)

        context = {
            **self.admin_site.each_context(request),
            "title": "Обнулить данные студентов",
            "opts": obj._meta,
            "students": students,
            "keep": keep,
            "confirm_word": RESET_CONFIRM_WORD,
            "cancel_url": change_url,
        }
        return TemplateResponse(request, "admin/operations/reset_students.html", context)

    @staticmethod
    def _spawn_period_quests() -> None:
        """Квесты на сегодня заводятся сразу, а не ночью: в день запуска они нужны с утра."""
        from apps.quests.services.quest_periods import ensure_period_quests

        ensure_period_quests()

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
