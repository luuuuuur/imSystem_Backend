from django.db import transaction
from ims_backend.models import Ambulancia, SuscritosAGrupo, DespachoPersonal, Despacho
from ims_backend.serializers import SenalOtroSerializer, SenalPatenteSerializer
from ims_backend.task_package.task_notificaciones import notificacion, Senal
from ims_backend.task_package.task_log_ambulancias import (
    log_senal_otro, log_senal_ambulancia, log_senal_ocupada, log_senal_outofservice,
    log_senal_disponible, log_senal_en_camino, log_senal_en_destino, log_senal_regresando,
)
from ims_backend.toolbox.exceptions import BadRequestException, NotFoundException

_SENALES_AMBULANCIA = {
    Senal.AMBULANCIA:   log_senal_ambulancia,
    Senal.OCUPADA:      log_senal_ocupada,
    Senal.OUTOFSERVICE: log_senal_outofservice,
}

_SENALES_EQUIPO = {
    Senal.DISPONIBLE: log_senal_disponible,
    Senal.EN_CAMINO:  log_senal_en_camino,
    Senal.EN_DESTINO:  log_senal_en_destino,
    Senal.REGRESANDO: log_senal_regresando,
}


def _obtener_contexto_equipo(usuario):
    grupo_nombre = f"Usuario {usuario.id}"
    despacho_id = None
    try:
        suscripcion = SuscritosAGrupo.objects.select_related('grupo').get(
            personal=usuario, fecha_salida=None
        )
        grupo_nombre = suscripcion.grupo.nombre_grupo
        dp = DespachoPersonal.objects.select_related('despacho').filter(
            grupo=suscripcion.grupo,
            despacho__estado__in=[Despacho.ASIGNADO, Despacho.EMERGENCIA]
        ).latest('id')
        despacho_id = dp.despacho.id
    except (SuscritosAGrupo.DoesNotExist, DespachoPersonal.DoesNotExist):
        pass
    return grupo_nombre, despacho_id


def _verificar_ambulancia(patente):
    try:
        Ambulancia.objects.get(patente=patente)
    except Ambulancia.DoesNotExist:
        raise NotFoundException(detail=f"No existe ambulancia con patente '{patente}'.")


def handle_signal(tipo, payload, usuario):
    uid = usuario.id

    match tipo:
        case Senal.OTRO:
            serializer = SenalOtroSerializer(data=payload)
            if not serializer.is_valid():
                raise BadRequestException(detail=serializer.errors)
            mensaje = serializer.validated_data["mensaje"]
            transaction.on_commit(lambda: notificacion.delay(type=Senal.OTRO, mensaje=mensaje, usuario_id=uid))
            transaction.on_commit(lambda: log_senal_otro.delay(usuario_id=uid, mensaje=mensaje))

        case Senal.AMBULANCIA | Senal.OCUPADA | Senal.OUTOFSERVICE:
            serializer = SenalPatenteSerializer(data=payload)
            if not serializer.is_valid():
                raise BadRequestException(detail=serializer.errors)
            patente = serializer.validated_data["patente"]
            _verificar_ambulancia(patente)
            _log_task = _SENALES_AMBULANCIA[tipo]
            transaction.on_commit(lambda: notificacion.delay(type=tipo, patente=patente, usuario_id=uid))
            transaction.on_commit(lambda: _log_task.delay(usuario_id=uid, patente=patente))

        case Senal.DISPONIBLE | Senal.EN_CAMINO | Senal.EN_DESTINO | Senal.REGRESANDO:
            grupo_nombre, despacho_id = _obtener_contexto_equipo(usuario)
            _log_task = _SENALES_EQUIPO[tipo]
            transaction.on_commit(lambda: notificacion.delay(type=tipo, grupo_nombre=grupo_nombre, despacho_id=despacho_id))
            transaction.on_commit(lambda: _log_task.delay(usuario_id=uid, grupo_nombre=grupo_nombre, despacho_id=despacho_id))

        case _:
            raise BadRequestException(detail="Tipo de señal no reconocido.")
