from django.db import transaction
from ims_backend.models import Ambulancia, SuscritosAGrupo, DespachoPersonal
from ims_backend.serializers import SenalOtroSerializer, SenalPatenteSerializer
from ims_backend.task_package.task_notificaciones import notificacion, Senal
from ims_backend.task_package.task_log_ambulancias import (
    log_senal_otro, log_senal_ambulancia, log_senal_ocupada, log_senal_outofservice,
    log_senal_disponible, log_senal_en_camino, log_senal_en_destino,
    log_senal_operando, log_senal_regresando,
)
from ims_backend.toolbox.exceptions import BadRequestException, NotFoundException

_SENALES_AMBULANCIA = {
    Senal.AMBULANCIA:   log_senal_ambulancia,
    Senal.OCUPADA:      log_senal_ocupada,
    Senal.OUTOFSERVICE: log_senal_outofservice,
}

_SENALES_DESPACHO = {
    Senal.EN_CAMINO:  log_senal_en_camino,
    Senal.EN_DESTINO: log_senal_en_destino,
    Senal.OPERANDO:   log_senal_operando,
}

_SENALES_GLOBAL = {
    Senal.DISPONIBLE: log_senal_disponible,
    Senal.REGRESANDO: log_senal_regresando,
}


def _obtener_grupo_desde_despacho(despacho_id):
    try:
        dp = DespachoPersonal.objects.select_related('grupo').filter(despacho_id=despacho_id).first()
        if dp is not None:
            return dp.grupo.nombre_grupo
    except Exception:
        pass
    return f"Despacho {despacho_id}"


def _obtener_grupo_desde_usuario(usuario):
    try:
        suscripcion = SuscritosAGrupo.objects.select_related('grupo').filter(
            personal=usuario, fecha_salida=None
        ).all()
        if suscripcion is not None:
            return suscripcion.grupo.nombre_grupo
    except Exception:
        pass
    return f"Usuario {usuario.id}"


def _verificar_ambulancia(patente):
    try:
        Ambulancia.objects.get(patente=patente)
    except Ambulancia.DoesNotExist:
        raise NotFoundException(detail=f"No existe ambulancia con patente '{patente}'.")


def handle_signal(tipo, payload, usuario, despacho_id=None):
    uid = usuario.id

    match tipo:
        case Senal.OTRO:
            serializer = SenalOtroSerializer(data=payload)
            if not serializer.is_valid():
                raise BadRequestException(detail=serializer.errors)
            mensaje = serializer.validated_data["mensaje"]
            transaction.on_commit(lambda: notificacion.delay(type=Senal.OTRO, mensaje=mensaje, usuario_id=uid))
            transaction.on_commit(lambda: log_senal_otro.delay(usuario_id=uid, mensaje=mensaje))
        #Operatividad no cambia estado
        case Senal.AMBULANCIA | Senal.OCUPADA | Senal.OUTOFSERVICE:
            serializer = SenalPatenteSerializer(data=payload)
            if not serializer.is_valid():
                raise BadRequestException(detail=serializer.errors)
            patente = serializer.validated_data["patente"]
            _verificar_ambulancia(patente)
            _log_task = _SENALES_AMBULANCIA[tipo]
            transaction.on_commit(lambda: notificacion.delay(type=tipo, patente=patente, usuario_id=uid))
            transaction.on_commit(lambda: _log_task.delay(usuario_id=uid, patente=patente))
        #Despacho no cambia estado
        case Senal.EN_CAMINO | Senal.EN_DESTINO | Senal.OPERANDO:
            if not despacho_id:
                raise BadRequestException(detail="Se requiere el parámetro 'despacho_id' para esta señal.")
            grupo_nombre = _obtener_grupo_desde_despacho(despacho_id)
            _log_task = _SENALES_DESPACHO[tipo]
            _did = despacho_id
            _gn  = grupo_nombre
            transaction.on_commit(lambda: notificacion.delay(type=tipo, grupo_nombre=_gn, despacho_id=_did))
            transaction.on_commit(lambda: _log_task.delay(usuario_id=uid, grupo_nombre=_gn, despacho_id=_did))
        #Nivel equipo
        case Senal.DISPONIBLE | Senal.REGRESANDO:
            grupo_nombre = _obtener_grupo_desde_usuario(usuario)
            _log_task = _SENALES_GLOBAL[tipo]
            _gn = grupo_nombre
            transaction.on_commit(lambda: notificacion.delay(type=tipo, grupo_nombre=_gn, despacho_id=None))
            transaction.on_commit(lambda: _log_task.delay(usuario_id=uid, grupo_nombre=_gn, despacho_id=None))

        case _:
            raise BadRequestException(detail="Tipo de señal no reconocido.")
