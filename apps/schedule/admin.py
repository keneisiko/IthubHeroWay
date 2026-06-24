from django.contrib import admin

from apps.operations.admin_rbac import ManagedRoleAdminMixin, is_curator, is_hq, is_tutor

from .models import Schedule


@admin.register(Schedule)
class ScheduleAdmin(ManagedRoleAdminMixin):
    list_display = ("squad", "day_of_week", "start_time", "end_time", "discipline", "is_active")
    list_filter = ("day_of_week", "is_active", "squad")
    search_fields = ("squad__code", "squad__name", "discipline")
    ordering = ("squad", "day_of_week", "start_time")

    def has_module_permission(self, request):
        return super().has_module_permission(request) and not is_hq(request.user)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("squad")
        if request.user.is_superuser or request.user.role == "admin":
            return qs
        if is_curator(request.user) and request.user.squad_id:
            return qs.filter(squad_id=request.user.squad_id)
        if is_tutor(request.user):
            return qs.filter(squad__course__gte=2, squad__course__lte=4)
        return qs.none()
