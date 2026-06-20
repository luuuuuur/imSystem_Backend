from ims_backend.models import LogAuditoria
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def update_inventario_log(self, data):
    try:
        log = f"El usuario con RUT {data['rut']} (ID: {data['user_id']}) actualizó el stock de la presentación con ID {data['presentacion_id']} en la ambulancia con ID {data['ambulancia_id']}. Cantidad registrada: {data['cantidad']}."
        LogAuditoria.objects.create(
            tipo="inventario", usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log
        )
    except Exception as exc:
        raise self.retry(exc=exc)