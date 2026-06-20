from ims_backend.models import LogAuditoria
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def agregar_personal_log(self, data):
    try:
        log = f"El usuario con RUT {data['rut']} (ID: {data['user_id']}) registró un nuevo trabajador con RUT {data['rut_trabajador']}."
        LogAuditoria.objects.create(tipo='despacho', usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)

