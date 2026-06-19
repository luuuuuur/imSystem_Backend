from ims_backend.models import LogAuditoria
from ims_backend.serializers import LogAuditoriaSerializer
from ims_backend.auth_package.permissions import ControlProfileOnly, MFAVerified
from ims_backend.toolbox.Paginators import BaseReadViewSet


class LogViewSet(BaseReadViewSet):
    queryset = LogAuditoria.objects.all().order_by('-id')
    http_method_names = ['get']
    serializer_class = LogAuditoriaSerializer
    permission_classes = [ControlProfileOnly & MFAVerified]
