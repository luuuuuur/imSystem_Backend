from ims_backend.serializers import CambiarEstadoAmbulancia
from ims_backend.models import Ambulancia, Personal
from django.db import transaction
from ims_backend.task_package.task_notificaciones import notificacion
from ims_backend.task_package.task_log_ambulancias import actualizar_estados
from ims_backend.toolbox.exceptions import InternalServerException, BadRequestException
def change_despacho_status(type, ambulancia: Ambulancia):
    match type:
        case Ambulancia.TRABAJANDO:
            ambulancia.estado_disponibilidad=Ambulancia.TRABAJANDO
            ambulancia.save(update_fields=["estado_disponibilidad"])
        case Ambulancia.DISPONIBLE:
            ambulancia.estado_disponibilidad=Ambulancia.DISPONIBLE
            ambulancia.save(update_fields=["estado_disponibilidad"])
        case Ambulancia.NO_SERVICE:
            ambulancia.estado_disponibilidad=Ambulancia.NO_SERVICE
            ambulancia.save(update_fields=["estado_disponibilidad"])
        case Ambulancia.MANTENCION:
            ambulancia.estado_disponibilidad=Ambulancia.MANTENCION
            ambulancia.save(update_fields=["estado_disponibilidad"])
        case Ambulancia.ENPREPARACION:
            ambulancia.estado_disponibilidad=Ambulancia.ENPREPARACION
            ambulancia.save(update_fields=["estado_disponibilidad"])
        case _:
            return
        
#TRANSACTION ON COMMIT -> LOG AUDITORIA, NOTIFICACION #SE CAMBIA ESTADO
def cambiar_estado(request):
    serializer = CambiarEstadoAmbulancia(data=request.query_params)
    if serializer.is_valid():
        valid_data = serializer.validated_data
        try:
            personal = Personal.objects.get(id=valid_data["conid"])
            ambulancia = Ambulancia.objects.get(id=valid_data["ambid"])
            estado = valid_data["estado"]
            with transaction.atomic():
                change_despacho_status(estado, ambulancia)
            transaction.on_commit(lambda: notificacion.delay(type=estado, patente=ambulancia.patente, estado=estado, id=personal.id))
            transaction.on_commit(lambda: actualizar_estados.delay(conid=personal.id, ambid=ambulancia.id))
            return True
        except Exception:
            raise InternalServerException
    else:
        raise BadRequestException



    