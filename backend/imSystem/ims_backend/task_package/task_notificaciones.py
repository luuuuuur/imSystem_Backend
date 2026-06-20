import logging
from celery import shared_task
from firebase_admin import messaging
from ims_backend.aws_package.secrets_manager import Secrets_API
import firebase_admin
from ims_backend.models import DeviceToken, Despacho, Atencion, Ambulancia

logger = logging.getLogger(__name__)

_firebase_app = None

def _init_app_firebase():
    global _firebase_app
    if _firebase_app is None:
        cred = firebase_admin.credentials.Certificate(Secrets_API.load_secrets_api())
        _firebase_app = firebase_admin.initialize_app(credential=cred)

def _send(token, _title, _body):
    if not token:
        logger.warning(f'[FCM] No hay tokens para enviar: title={_title}')
        return
    logger.info(f'[FCM] Enviando "{_title}" a {len(token)} dispositivo(s): {token}')
    _message = messaging.Notification(title=_title, body=_body)
    _multicast_message = messaging.MulticastMessage(tokens=token, notification=_message)
    response = messaging.send_each_for_multicast(multicast_message=_multicast_message, app=_firebase_app)
    logger.info(f'[FCM] Resultado: {response.success_count} exitosos, {response.failure_count} fallidos')
    for i, r in enumerate(response.responses):
        if r.success:
            logger.info(f'[FCM] Token[{i}] {token[i][:20]}... -> SUCCESS')
        else:
            logger.error(f'[FCM] Token[{i}] {token[i][:20]}... -> FAILED: {r.exception}')

def _tokens_por_grupo(grupo_id):
    return list(DeviceToken.objects.filter(
        usuario__grupo_personal__grupo_id=grupo_id,
        usuario__grupo_personal__fecha_salida=None,
    ).values_list('device_token', flat=True))

def _tokens_por_rol(nombre_rol):
    return list(DeviceToken.objects.filter(
        usuario__rol__nombre_rol=nombre_rol,
        usuario__is_active=True,
    ).values_list('device_token', flat=True))

def _enviar_despacho_asignado(grupo_id, despacho_id):
    token = _tokens_por_grupo(grupo_id)
    logger.info(f'[FCM] despacho_asignado: grupo_id={grupo_id}, tokens={len(token)}')
    _send(token=token, _title="Nuevo despacho asignado", _body=f"Se te ha asignado el despacho con ID {despacho_id}. Revisa los detalles y prepara al equipo.")

def _enviar_despacho_programado(grupo_id, fecha):
    token = _tokens_por_grupo(grupo_id)
    logger.info(f'[FCM] despacho_programado: grupo_id={grupo_id}, tokens={len(token)}')
    _send(token=token, _title="Nuevo despacho programado", _body=f"Se te ha asignado un despacho para el {fecha}. Revisa los detalles en el sistema y prepárate con anticipación.")

def _enviar_despacho_finalizado(despacho_id):
    token = _tokens_por_rol('control')
    logger.info(f'[FCM] despacho_finalizado: despacho_id={despacho_id}, tokens={len(token)}')
    _send(token=token, _title="Despacho finalizado", _body=f"El equipo ha completado el despacho con ID {despacho_id}. Ingresa al sistema para revisar el resumen y cerrar el registro.")

def _enviar_atencion_registrada(fecha):
    token = _tokens_por_rol('control')
    logger.info(f'[FCM] atencion_registrada: fecha={fecha}, tokens={len(token)}')
    _send(token=token, _title="Nueva atención registrada", _body=f"Se ha registrado una nueva atención el {fecha}. Ingresa al sistema para revisar los detalles del caso.")

def _enviar_despacho_emergencia(dir, grupo_id):
    token = _tokens_por_grupo(grupo_id)
    logger.info(f'[FCM] emergencia: grupo_id={grupo_id}, dir={dir}, tokens={len(token)}')
    _send(token=token, _title="Alerta de emergencia", _body=f"Se ha activado una alerta de emergencia. Dirígete de inmediato a: {dir}. Activa el protocolo de respuesta urgente.")

def _enviar_estado_ambulancia(patente, estado, id):
    token = _tokens_por_rol('control')
    logger.info(f'[FCM] Estado ambulancia: Se cambió el estado de la ambulancia con patente {patente}, tokens={len(token)}')
    _send(token=token, _title="Cambio de estado de ambulancia", _body=f"La ambulancia con patente {patente} ha actualizado su estado a '{estado}'. Acción registrada por el usuario con ID {id}.")
@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def notificacion(self, type, **kwargs):
    try:
        logger.info(f'[FCM] Tarea notificacion iniciada: type={type}, kwargs={kwargs}')
        _init_app_firebase()
        match type:
            case Despacho.ASIGNADO:
                _enviar_despacho_asignado(kwargs["grupo_id"], kwargs["despacho_id"])
            case Despacho.PROGRAMADO:
                _enviar_despacho_programado(kwargs["grupo_id"], kwargs["fecha"])
            case Despacho.FINALIZADO:
                _enviar_despacho_finalizado(kwargs["despacho_id"])
            case Atencion.REGISTRADA:
                _enviar_atencion_registrada(kwargs["fecha"])
            case Despacho.EMERGENCIA:
                _enviar_despacho_emergencia(kwargs["dir"], kwargs["grupo_id"])
            case Ambulancia.DISPONIBLE:
                _enviar_estado_ambulancia(kwargs["patente"], kwargs["estado"], kwargs["id"])
            case Ambulancia.ENPREPARACION:
                _enviar_estado_ambulancia(kwargs["patente"], kwargs["estado"], kwargs["id"])
            case Ambulancia.TRABAJANDO:
                _enviar_estado_ambulancia(kwargs["patente"], kwargs["estado"], kwargs["id"])
            case Ambulancia.MANTENCION:
                _enviar_estado_ambulancia(kwargs["patente"], kwargs["estado"], kwargs["id"])
            case Ambulancia.NO_SERVICE:
                _enviar_estado_ambulancia(kwargs["patente"], kwargs["estado"], kwargs["id"])    
            case _:
                logger.warning(f'[FCM] Tipo de notificacion no reconocido: {type}')
                return
    except Exception as exc:
        logger.error(f'[FCM] Error en tarea notificacion: {exc}')
        raise self.retry(exc=exc)