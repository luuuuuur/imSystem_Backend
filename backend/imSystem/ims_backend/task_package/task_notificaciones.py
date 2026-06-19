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

def _enviar_despacho_programado(grupo_id, fecha):
    token = list(
        DeviceToken.objects.filter(
            usuario__grupo_personal__grupo_id=grupo_id,
            usuario__grupo_personal__fecha_salida=None,
        ).values_list('device_token', flat=True)
    )
    logger.info(f'[FCM] despacho_programado: grupo_id={grupo_id}, tokens={len(token)}')
    _send(token=token, _title="Programacion de Despacho", _body=f"Se te ha programado un despacho con fecha {fecha}")

def _enviar_despacho_finalizado(despacho_id):
    _token = list(
        DeviceToken.objects.filter(
            usuario__rol__nombre_rol='control',
            usuario__is_active=True
        ).values_list('device_token', flat=True)
    )
    logger.info(f'[FCM] despacho_finalizado: despacho_id={despacho_id}, tokens={len(_token)}')
    _send(token=_token, _title="Despacho finalizado", _body=f"El equipo ha finalizado el despacho, id: {despacho_id}")

def _enviar_atencion_registrada(fecha):
    token = list(DeviceToken.objects.filter(
        usuario__rol__nombre_rol='control',
        usuario__is_active=True
    ).values_list('device_token', flat=True))
    logger.info(f'[FCM] atencion_registrada: fecha={fecha}, tokens={len(token)}')
    _send(token=token, _title="Se ha registrado una atencion", _body=f"Se ha registrado la atencion con fecha: {fecha}")

def _enviar_despacho_emergencia(dir, grupo_id):
    token = list(
        DeviceToken.objects.filter(
            usuario__grupo_personal__grupo_id=grupo_id,
            usuario__grupo_personal__fecha_salida=None
        ).values_list('device_token', flat=True)
    )
    logger.info(f'[FCM] emergencia: grupo_id={grupo_id}, dir={dir}, tokens={len(token)}')
    _send(token=token, _title="Emergencia", _body=f"Se te ha llamado por una situación de emergencia, favor de dirigirse a la siguiente direccion lo antes posible: {dir}")
def _enviar_estado_ambulancia(patente, estado, id):
    token = list(DeviceToken.objects.filter(
        usuario__rol__nombre_rol='control',
        usuario__is_active=True
    ).values_list('device_token', flat=True))
    logger.info(f'[FCM] Estado ambulancia: Se cambio el estado de la ambulancia con patente: {patente}, tokens={len(token)}')
    _send(token=token, _title="Ambulancia", _body=f"Usuario con ID: {id}, Ambulancia con patente: {patente} ha cambiado a: {estado}")
@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def notificacion(self, type, **kwargs):
    try:
        logger.info(f'[FCM] Tarea notificacion iniciada: type={type}, kwargs={kwargs}')
        _init_app_firebase()
        match type:
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