from ims_backend.models import LogAuditoria
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def agregar_paciente_log(self, data):
    try:
        log = f"""El usuario con rut: {data["rut"]} y id: {data["id"]}, agregó al paciente con rut: {data["paciente_rut"]}"""
        LogAuditoria.objects.create(tipo="paciente",usuario_id=data["id"],rut=data["rut"], descripcion=log )
    except Exception as exc:
        raise self.retry(exc=exc)