from backend.imSystem.ims_backend.models import LogAuditoria
from celery import shared_task

@shared_task
def agregar_personal_log(data):
    log = f"""El usuario con rut: {data["rut"]} y id: {data["user_id"]}. Agregró un nuevo trabajador con rut: {data["rut_trabajador"]}"""
    LogAuditoria.objects.create(tipo='despacho', usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
