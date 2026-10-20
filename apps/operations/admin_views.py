from __future__ import annotations

from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.integrations.services.account_gate import agents_for_scoring
from apps.operations.services.review_queue import pending_proofs
from apps.progress.models import RatingLog
from apps.progress.services.rating_zones import red_zone_max, risk_zone_max, zone_bounds
from apps.quests.models import SeasonalEvent


def _zone_counts(users_qs):
    """Распределение по зонам рейтинга — одним запросом вместо шести.

    Функция вызывается на каждом из трёх дашбордов, поэтому шесть отдельных
    COUNT заметно утяжеляли рендер.
    """
    # Границы берутся из rating_zones, а не дублируются здесь.
    annotations = {}
    for code, lower, upper in zone_bounds():
        condition = Q(rating_current__gte=lower)
        if upper is not None:
            condition &= Q(rating_current__lt=upper)
        annotations[code] = Count("pk", filter=condition)
    return users_qs.aggregate(**annotations)


def _rating_dynamics(users_qs, days=7):
    """Суммарное изменение рейтинга по дням.

    Было две ошибки: агрегат `Count("id")` присваивался полю `total_delta`,
    то есть график «динамики рейтинга» показывал количество записей журнала,
    а не сумму изменений; и группировка шла сырым SQL `date(created_at)`
    по timestamptz, то есть по UTC, а не по часовому поясу проекта.
    """
    start = timezone.now() - timedelta(days=days)
    buckets = (
        RatingLog.objects.filter(user__in=users_qs, created_at__gte=start)
        .annotate(day=TruncDate("created_at", tzinfo=timezone.get_current_timezone()))
        .values("day")
        .annotate(total_delta=Sum("delta"), changes=Count("id"))
        .order_by("day")
    )
    return [
        {"x": str(x["day"]), "y": x["total_delta"] or 0, "changes": x["changes"]}
        for x in buckets
    ]


def _students():
    """Студенты, которых показывают дашборды.

    Раньше все три дашборда брали только привязавших Telegram. Бот три
    недели не получал сообщений, и по Положению (п. 2.1–2.2) привязка
    больше не условие — куратор видел почти пустой дашборд. Теперь та же
    аудитория, что у начислений, и её задаёт «Настройки платформы».
    """
    return agents_for_scoring(User.objects.filter(role=Role.AGENT))


def _sees_everything(user) -> bool:
    return bool(user.is_superuser or user.role == Role.ADMIN)


@staff_member_required
def my_dashboard(request):
    """Одна ссылка «Мой дашборд» вместо трёх.

    В меню висели три дашборда, каждый открывался только своей роли, а
    остальным отвечал 403 — в том числе администратору на всех трёх.
    """
    role = request.user.role
    if role == Role.CURATOR:
        return redirect("admin-curator-dashboard")
    if role == Role.TUTOR:
        return redirect("admin-tutor-dashboard")
    if role == Role.HQ or _sees_everything(request.user):
        return redirect("admin-hq-dashboard")
    raise PermissionDenied("Для вашей роли дашборда нет")


@staff_member_required
def curator_dashboard(request):
    if not (request.user.is_superuser or request.user.role == Role.CURATOR):
        raise PermissionDenied("Доступ запрещён для вашей роли")
    users_qs = _students().filter(squad_id=request.user.squad_id) if request.user.squad_id else User.objects.none()
    pending_qs = pending_proofs(request.user)
    context = {
        "zone_counts": _zone_counts(users_qs),
        "red_zone_users": users_qs.filter(rating_current__lt=red_zone_max()).order_by("rating_current")[:20],
        "rating_dynamics": _rating_dynamics(users_qs, days=30),
        "seasonal_events": SeasonalEvent.objects.filter(is_active=True).order_by("-created_at")[:5],
        "pending_self_reports_count": pending_qs.count(),
        "pending_self_reports": pending_qs[:5],
    }
    return render(request, "admin/dashboards/curator.html", context)


@staff_member_required
def tutor_dashboard(request):
    if not (_sees_everything(request.user) or request.user.role == Role.TUTOR):
        raise PermissionDenied("Доступ запрещён для вашей роли")
    users_qs = _students().filter(squad__course__gte=2, squad__course__lte=4)
    pending_qs = pending_proofs(request.user)
    context = {
        "zone_counts": _zone_counts(users_qs),
        "risk_users": users_qs.filter(rating_current__lt=risk_zone_max()).order_by("rating_current")[:30],
        "red_zone_users": users_qs.filter(rating_current__lt=red_zone_max()).order_by("rating_current")[:20],
        "rating_dynamics": _rating_dynamics(users_qs, days=30),
        "seasonal_events": SeasonalEvent.objects.filter(is_active=True).order_by("-created_at")[:5],
        "pending_self_reports_count": pending_qs.count(),
        "pending_self_reports": pending_qs[:5],
    }
    return render(request, "admin/dashboards/tutor.html", context)


@staff_member_required
def hq_dashboard(request):
    if not (_sees_everything(request.user) or request.user.role == Role.HQ):
        raise PermissionDenied("Доступ запрещён для вашей роли")
    users_qs = _students()
    context = {
        "zone_counts": _zone_counts(users_qs),
        "red_zone_users": users_qs.filter(rating_current__lt=red_zone_max()).order_by("rating_current")[:20],
        "rating_dynamics": _rating_dynamics(users_qs, days=7),
        "seasonal_events": SeasonalEvent.objects.order_by("-created_at")[:10],
    }
    return render(request, "admin/dashboards/hq.html", context)
