from ims_backend.models import LogAuditoria
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def agregar_personal_log(self, data):
    try:
        log = f"""El usuario con rut: {data["rut"]} y id: {data["user_id"]}. Agregró un nuevo trabajador con rut: {data["rut_trabajador"]}"""
        LogAuditoria.objects.create(tipo='despacho', usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)

