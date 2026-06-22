from ims_backend.serializers import CambiarEstadoAmbulancia
from ims_backend.models import Ambulancia
from django.db import transaction
from ims_backend.task_package.task_notificaciones import notificacion
from ims_backend.task_package.task_log_ambulancias import actualizar_estados
from ims_backend.toolbox.exceptions import InternalServerException, BadRequestException
_ESTADOS_VALIDOS = {
    Ambulancia.DISPONIBLE, Ambulancia.TRABAJANDO, Ambulancia.NO_SERVICE,
    Ambulancia.MANTENCION, Ambulancia.ENPREPARACION,
}

def change_despacho_status(type, ambulancia: Ambulancia):
    if type in _ESTADOS_VALIDOS:
        ambulancia.estado_disponibilidad = type
        ambulancia.save(update_fields=["estado_disponibilidad"])
        
#TRANSACTION ON COMMIT -> LOG AUDITORIA, NOTIFICACION #SE CAMBIA ESTADO
def cambiar_estado(query_params, rut):
    serializer = CambiarEstadoAmbulancia(data=query_params)
    if serializer.is_valid():
        valid_data = serializer.validated_data
        try:
            ambulancia = Ambulancia.objects.get(id=valid_data["ambid"])
            estado = valid_data["estado"]
            with transaction.atomic():
                change_despacho_status(estado, ambulancia)
            transaction.on_commit(lambda: actualizar_estados.delay(rut=rut, ambid=ambulancia.id))
            return True
        except Exception:
            raise InternalServerException
    else:
        raise BadRequestException



    