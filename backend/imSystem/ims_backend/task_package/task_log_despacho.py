from ims_backend.models import LogAuditoria
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def crear_despacho_log(self, data):
    try:
        log = (f"El usuario con rut: {data["rut"]} y id: {data["user_id"]}. Creó un despacho con id: {data["id"]} para el paciente con rut: {data["paciente_rut"]}")
        LogAuditoria.objects.create(tipo='despacho', usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def asignar_despacho_log(self,data):
    try:
        log = (
            f"El usuario con rut: {data['rut']}. Asignó un despacho con id: {data['id']} para el grupo con nombre: {data['nombre_grupo']} y id: {data['grupo_id']} y la ambulancia: {data['patente']}"
        )
        LogAuditoria.objects.create(tipo='despacho', usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def cambiar_estado_log(self, data):
    try:
        log = (f"El usuario {data["rut"]} ha cambiado el estado del despacho con id: {data["despacho_id"]} a {data["estado"]}")
        LogAuditoria.objects.create(tipo='despacho', usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)