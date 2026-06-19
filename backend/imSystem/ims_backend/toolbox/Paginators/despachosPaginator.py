from rest_framework.pagination import CursorPagination
from rest_framework.viewsets import ReadOnlyModelViewSet
from django.db.models import Prefetch
from ims_backend.models import Despacho, DespachoPersonal, SuscritosAGrupo
from ims_backend.serializers import DespachoListSerializer
from ims_backend.auth_package.permissions import ControlProfileOnly, MFAVerified

_members_qs = SuscritosAGrupo.objects.filter(
    fecha_salida=None
).select_related('personal', 'personal__rol')

_equipo_qs = DespachoPersonal.objects.select_related('grupo').prefetch_related(
    Prefetch('grupo__grupo_nombre', queryset=_members_qs, to_attr='miembros_activos')
)

# Derived at import time from the model — stays in sync with Despacho.ESTADOS automatically
_VALID_ESTADOS = {value for value, _ in Despacho.ESTADOS}

class StandarPaginator(CursorPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 10
    ordering = '-id'

class DespachoViewSet(ReadOnlyModelViewSet):
    queryset = Despacho.objects.select_related('paciente').prefetch_related(
        Prefetch('equipo', queryset=_equipo_qs, to_attr='equipo_prefetch')
    ).order_by('-id')
    serializer_class = DespachoListSerializer
    pagination_class = StandarPaginator
    http_method_names = ['get']
    permission_classes = [MFAVerified & ControlProfileOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        estado = self.request.query_params.get('estado')
        if estado and estado in _VALID_ESTADOS:
            qs = qs.filter(estado=estado)
        return qs
