from __future__ import annotations

from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.progress.models import RatingLog
from apps.quests.models import SeasonalEvent, SelfReportProof, SelfReportProofStatus


def _zone_counts(users_qs):
    counts = {
        "red": users_qs.filter(rating_current__lt=100).count(),
        "orange": users_qs.filter(rating_current__gte=100, rating_current__lt=200).count(),
        "yellow": users_qs.filter(rating_current__gte=200, rating_current__lt=400).count(),
        "green": users_qs.filter(rating_current__gte=400, rating_current__lt=650).count(),
        "platinum": users_qs.filter(rating_current__gte=650, rating_current__lt=850).count(),
        "gold": users_qs.filter(rating_current__gte=850).count(),
    }
    return counts


def _rating_dynamics(users_qs, days=7):
    start = timezone.now() - timedelta(days=days)
    buckets = (
        RatingLog.objects.filter(user__in=users_qs, created_at__gte=start)
        .extra(select={"day": "date(created_at)"})
        .values("day")
        .annotate(total_delta=Count("id"))
        .order_by("day")
    )
    return [{"x": str(x["day"]), "y": x["total_delta"]} for x in buckets]


@staff_member_required
def curator_dashboard(request):
    if not (request.user.is_superuser or request.user.role == Role.CURATOR):
        raise PermissionDenied("Доступ запрещён для вашей роли")
    users_qs = (
        User.objects.filter(squad_id=request.user.squad_id, role=Role.AGENT, telegram_link__is_active=True)
        if request.user.squad_id
        else User.objects.none()
    )
    pending_qs = (
        SelfReportProof.objects.filter(
            status=SelfReportProofStatus.PENDING, user__squad_id=request.user.squad_id
        )
        .select_related("user", "quest")
        .order_by("-created_at")
    )
    context = {
        "zone_counts": _zone_counts(users_qs),
        "red_zone_users": users_qs.filter(rating_current__lt=100).order_by("rating_current")[:20],
        "rating_dynamics": _rating_dynamics(users_qs, days=30),
        "seasonal_events": SeasonalEvent.objects.filter(is_active=True).order_by("-created_at")[:5],
        "pending_self_reports_count": pending_qs.count(),
        "pending_self_reports": pending_qs[:5],
    }
    return render(request, "admin/dashboards/curator.html", context)


@staff_member_required
def tutor_dashboard(request):
    if not (request.user.is_superuser or request.user.role == Role.TUTOR):
        raise PermissionDenied("Доступ запрещён для вашей роли")
    users_qs = User.objects.filter(
        squad__course__gte=2,
        squad__course__lte=4,
        role=Role.AGENT,
        telegram_link__is_active=True,
    )
    pending_qs = (
        SelfReportProof.objects.filter(
            status=SelfReportProofStatus.PENDING, user__squad__course__gte=2, user__squad__course__lte=4
        )
        .select_related("user", "quest")
        .order_by("-created_at")
    )
    context = {
        "zone_counts": _zone_counts(users_qs),
        "risk_users": users_qs.filter(rating_current__lt=200).order_by("rating_current")[:30],
        "red_zone_users": users_qs.filter(rating_current__lt=100).order_by("rating_current")[:20],
        "rating_dynamics": _rating_dynamics(users_qs, days=30),
        "seasonal_events": SeasonalEvent.objects.filter(is_active=True).order_by("-created_at")[:5],
        "pending_self_reports_count": pending_qs.count(),
        "pending_self_reports": pending_qs[:5],
    }
    return render(request, "admin/dashboards/tutor.html", context)


@staff_member_required
def hq_dashboard(request):
    if not (request.user.is_superuser or request.user.role == Role.HQ):
        raise PermissionDenied("Доступ запрещён для вашей роли")
    users_qs = User.objects.filter(role=Role.AGENT, telegram_link__is_active=True)
    context = {
        "zone_counts": _zone_counts(users_qs),
        "red_zone_users": users_qs.filter(rating_current__lt=100).order_by("rating_current")[:20],
        "rating_dynamics": _rating_dynamics(users_qs, days=7),
        "seasonal_events": SeasonalEvent.objects.order_by("-created_at")[:10],
    }
    return render(request, "admin/dashboards/hq.html", context)
