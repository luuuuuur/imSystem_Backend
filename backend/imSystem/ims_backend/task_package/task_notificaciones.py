from celery import shared_task
from firebase_admin import messaging
from ims_backend.aws_package.secrets_manager import Secrets_API
import firebase_admin
from ims_backend.models import DeviceToken, Despacho,Atencion
_firebase_app = None
def _init_app_firebase():
    global _firebase_app
    if _firebase_app is None:
        cred = firebase_admin.credentials.Certificate(Secrets_API.load_secrets_api())
        _firebase_app = firebase_admin.initialize_app(credential=cred) 


#SENDER
def _send(token, _title, _body):
    _message = messaging.Notification(title=_title, body=_body)
    _multicast_message= messaging.MulticastMessage(tokens=token,notification=_message)
    messaging.send_each_for_multicast(multicast_message=_multicast_message, app=_firebase_app)

def _enviar_despacho_programado(grupo_id, fecha):
        token = list(
                DeviceToken.objects.filter(
                    usuario__grupo_personal__grupo_id=grupo_id,
                    usuario__grupo_personal__fecha_salida=None,
                ).values_list('device_token', flat= True)
            )
        _send(token=token, _title=f"Programacion de Despacho", _body=f"Se te ha programado un despacho con fecha{fecha}")

def _enviar_despacho_finalizado(despacho_id):
    _token = list(
                DeviceToken.objects.filter(
                    usuario__rol__nombre_rol ='control',
                    usuario__is_active = True
                ).values_list('device_token',flat=True)
        )
    _send(token=_token, _title=f"Despacho finalizado", _body=f"El equipo ha finalizado el despacho, id: {despacho_id}")


def _enviar_atencion_registrada(fecha):
    token = list(DeviceToken.objects.filter(
        usuario__rol__nombre_rol = 'control',
        usuario__is_active=True
    ).values_list('device_token', flat=True))
    _send(token=token, _title=f"Se ha registrado una atencion", _body=f"Se ha registrado la atencion con fecha:{fecha}")

def _enviar_despacho_emergencia(dir, grupo_id):
        token = list(
                DeviceToken.objects.filter(
                    usuario__grupo_personal__grupo_id=grupo_id,
                    usuario__grupo_personal__fecha_salida=None
                ).values_list('device_token', flat=True)
        )
        _send(token=token, _title="Emergencia", _body= f"Se te ha llamado por una situación de emergencia, favor de dirigirse a la siguiente direccion lo antes posible: {dir}")
#noti por grupos!!
@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def notificacion(self,type, **kwargs):
    try:
        _init_app_firebase()
        match type:
            #Despacho Programado
            case Despacho.PROGRAMADO:
                _enviar_despacho_programado(kwargs["grupo_id"], kwargs["fecha"])
            #Despacho Finalizado
            case Despacho.FINALIZADO:
                _enviar_despacho_finalizado(kwargs["despacho_id"])
            #Atencion Creada
            case Atencion.REGISTRADA:
                _enviar_atencion_registrada(kwargs["fecha"])
            #Emergencia
            case "EMER":
                _enviar_despacho_emergencia(kwargs["dir"], kwargs["grupo_id"])
            #None
            case _:
                return
    except Exception as exc:
        raise self.retry(exc=exc)