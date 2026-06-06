from celery import shared_task
from ims_backend.models import LogAuditoria, Personal
@shared_task(bind=True, max_retries=None, default_retry_delay=60)
def agregar_log_atencion(self, documento):
    try:
        user = Personal.objects.get(rut=documento["registrado_por"]["rut"])
        LogAuditoria.objects.create(tipo="atencion",atencion_id=documento["atencion"]["id"],usuario_id=user.id, 
                                    rut_usuario=documento["registrado_por"]["rut"],descripcion=
                                    f"Registró una atención:{documento["atencion"]["id"]}")
    except Exception as exc:
        raise self.retry(exc=exc)
