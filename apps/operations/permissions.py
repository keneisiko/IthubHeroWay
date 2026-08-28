from rest_framework.permissions import BasePermission

STAFF_ROLES = {"curator", "tutor", "admin", "hq"}


class IsStaffRole(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "role", None) in STAFF_ROLES)

