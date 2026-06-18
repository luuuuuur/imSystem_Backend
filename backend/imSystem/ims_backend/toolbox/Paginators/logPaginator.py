from rest_framework.pagination import CursorPagination
from rest_framework.viewsets import ReadOnlyModelViewSet
from ims_backend.models import LogAuditoria
from ims_backend.serializers import LogAuditoriaSerializer
from ims_backend.auth_package.permissions import ControlProfileOnly, MFAVerified
class StandarPaginator(CursorPagination):
    page_size=10
    page_size_query_param='page_size'
    max_page_size=10
    ordering='-id'

class LogViewSet(ReadOnlyModelViewSet): 
    queryset = LogAuditoria.objects.all().order_by('-id')
    serializer_class=LogAuditoriaSerializer
    pagination_class=StandarPaginator
    http_method_names = ['get']
    permission_classes = [ControlProfileOnly & MFAVerified]


