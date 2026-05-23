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