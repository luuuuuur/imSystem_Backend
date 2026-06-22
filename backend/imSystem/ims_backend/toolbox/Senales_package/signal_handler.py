from django.db import transaction
from ims_backend.models import Ambulancia
from ims_backend.serializers import SenalOtroSerializer, SenalPatenteSerializer
from ims_backend.task_package.task_notificaciones import notificacion, Senal
from ims_backend.toolbox.exceptions import BadRequestException, NotFoundException, InternalServerException

_TYPE_TO_ESTADO = {
    Senal.AMBULANCIA:   Ambulancia.ENPREPARACION,
    Senal.OCUPADA:      Ambulancia.TRABAJANDO,
    Senal.OUTOFSERVICE: Ambulancia.NO_SERVICE,
}


def _cambiar_estado_ambulancia(patente, nuevo_estado):
    try:
        ambulancia = Ambulancia.objects.get(patente=patente)
    except Ambulancia.DoesNotExist:
        raise NotFoundException(detail=f"No existe ambulancia con patente '{patente}'.")
    ambulancia.estado_disponibilidad = nuevo_estado
    ambulancia.save(update_fields=["estado_disponibilidad"])


def handle_signal(tipo, payload, usuario):
    if tipo == Senal.OTRO:
        serializer = SenalOtroSerializer(data=payload)
        if not serializer.is_valid():
            raise BadRequestException(detail=serializer.errors)
        mensaje = serializer.validated_data["mensaje"]
        transaction.on_commit(lambda: notificacion.delay(
            type=Senal.OTRO, mensaje=mensaje, usuario_id=usuario.id
        ))
        return

    if tipo in _TYPE_TO_ESTADO:
        serializer = SenalPatenteSerializer(data=payload)
        if not serializer.is_valid():
            raise BadRequestException(detail=serializer.errors)
        patente = serializer.validated_data["patente"]
        nuevo_estado = _TYPE_TO_ESTADO[tipo]
        try:
            with transaction.atomic():
                _cambiar_estado_ambulancia(patente, nuevo_estado)
            transaction.on_commit(lambda: notificacion.delay(
                type=tipo, patente=patente, usuario_id=usuario.id
            ))
        except NotFoundException:
            raise
        except Exception:
            raise InternalServerException
        return

    raise BadRequestException(detail="Tipo de señal no reconocido.")
