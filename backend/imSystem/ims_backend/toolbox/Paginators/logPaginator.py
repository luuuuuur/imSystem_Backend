from ims_backend.models import LogAuditoria
from ims_backend.serializers import LogAuditoriaSerializer
from ims_backend.auth_package.permissions import ControlProfileOnly, MFAVerified
from ims_backend.toolbox.Paginators import BaseReadViewSet, StandardCursorPagination


class LogCursorPagination(StandardCursorPagination):
    ordering = '-id'


class LogViewSet(BaseReadViewSet):
    queryset = LogAuditoria.objects.all()
    http_method_names = ['get']
    serializer_class = LogAuditoriaSerializer
    permission_classes = [ControlProfileOnly & MFAVerified]
    pagination_class = LogCursorPagination
