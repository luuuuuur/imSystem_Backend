from ims_backend.models import LogAuditoria
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def crear_despacho_log(self, data):
    try:
        log = f"El usuario con RUT {data['rut']} (ID: {data['user_id']}) creó el despacho con ID {data['id']} para el paciente con RUT {data['paciente_rut']}."
        LogAuditoria.objects.create(tipo='despacho', usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def asignar_despacho_log(self,data):
    try:
        log = f"El usuario con RUT {data['rut']} asignó el despacho con ID {data['id']} al grupo '{data['nombre_grupo']}' (ID: {data['grupo_id']}) con la ambulancia de patente {data['patente']}."
        LogAuditoria.objects.create(tipo='despacho', usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def cambiar_estado_log(self, data):
    try:
        log = f"El usuario con RUT {data['rut']} cambió el estado del despacho con ID {data['despacho_id']} a '{data['estado']}'."
        LogAuditoria.objects.create(tipo='despacho', usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)