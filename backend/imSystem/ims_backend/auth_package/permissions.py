from rest_framework.permissions import BasePermission


class ControlProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol and request.user.rol.nombre_rol == 'control')


class MedicProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol and request.user.rol.nombre_rol == 'medic')


class NurseProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol and request.user.rol.nombre_rol == 'nurse')


class DriverProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol and request.user.rol.nombre_rol == 'driver')


class MFAVerified(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated and request.session.get("mfa_verified", False)
        )


def roles_required(*roles: str) -> type[BasePermission]:
    """
    Returns a permission class that passes only when the user is MFA-verified
    and their role is one of the given roles.

    Usage:
        permission_classes = [roles_required('control', 'medic')]
    """
    allowed = frozenset(roles)

    class _Permission(BasePermission):
        def has_permission(self, request, view):
            return bool(
                request.user
                and request.user.is_authenticated
                and request.session.get('mfa_verified', False)
                and request.user.rol
                and request.user.rol.nombre_rol in allowed
            )

    return _Permission


# Prebuilt shorthands — avoids re-creating the class on every request for the
# most common combinations used across views.
MFAAndAnyProfile     = roles_required('control', 'driver', 'nurse', 'medic')
MFAAndClinicalProfile = roles_required('control', 'nurse', 'medic')
MFAAndMedicalStaff   = roles_required('nurse', 'medic')
MFAAndFieldStaff     = roles_required('driver', 'nurse', 'medic')
