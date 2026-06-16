from django.contrib import admin

from apps.operations.admin_rbac import ManagedRoleAdminMixin

from .models import Schedule


@admin.register(Schedule)
class ScheduleAdmin(ManagedRoleAdminMixin):
    list_display = ("squad", "day_of_week", "start_time", "end_time", "discipline", "is_active")
    list_filter = ("day_of_week", "is_active", "squad")
    search_fields = ("squad__code", "squad__name", "discipline")
    ordering = ("squad", "day_of_week", "start_time")
