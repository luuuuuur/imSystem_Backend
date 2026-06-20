from ims_backend.models import LogAuditoria
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def crear_grupo_log(self, data):
    try:
        ruts = [str(p) for p in data["personal"]]
        log = f"El usuario con RUT {data['rut']} (ID: {data['user_id']}) creó el grupo '{data['nombre_grupo']}' y asignó los siguientes RUTs: {', '.join(ruts)}."
        LogAuditoria.objects.create(tipo="grupo", usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def agregar_miembros_log(self, data):
    try:
        log = f"El usuario con RUT {data['rut']} (ID: {data['user_id']}) agregó al miembro con RUT {data['personal_rut']} al grupo '{data['group_nombre']}' (ID: {data['group_id']})."
        LogAuditoria.objects.create(tipo="grupo", usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def actualizar_estado_miembros_log(self, data):
    try:
        log = f"El usuario con RUT {data['rut']} (ID: {data['user_id']}) desacopló al miembro con RUT {data['personal_rut']} del grupo '{data['group_name']}' (ID: {data['group_id']})."
        LogAuditoria.objects.create(tipo="grupo", usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)