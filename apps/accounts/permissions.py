from rest_framework.permissions import SAFE_METHODS, BasePermission

STAFF_ROLES = {"curator", "tutor", "admin", "hq"}


class IsStaffRole(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "role", None) in STAFF_ROLES)


class IsSelfOrStaffRole(BasePermission):
    """
    Разрешает доступ к объекту пользователя, если это свой объект,
    либо если роль staff (curator/tutor/admin/hq).
    """

    def has_object_permission(self, request, view, obj) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "role", None) in STAFF_ROLES:
            return True
        return obj.pk == user.pk


class ReadOnly(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.method in SAFE_METHODS


class RolePermission(BasePermission):
    allowed_roles: set[str] = set()

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "role", None) in self.allowed_roles)


class IsAgent(RolePermission):
    allowed_roles = {"agent"}


class IsCurator(RolePermission):
    allowed_roles = {"curator"}


class IsTutor(RolePermission):
    allowed_roles = {"tutor"}


class IsAdmin(RolePermission):
    allowed_roles = {"admin"}


class IsHQ(RolePermission):
    allowed_roles = {"hq"}


class IsStaffLike(RolePermission):
    allowed_roles = {"curator", "tutor", "admin", "hq"}


class IsKnownRole(RolePermission):
    allowed_roles = {"agent", "curator", "tutor", "admin", "hq"}

