from ims_backend.models import LogAuditoria
from celery import shared_task

@shared_task
def agregar_paciente_log(data):
    log = f"""El usuario con rut: {data["rut"]} y id: {data["id"]}, agregó al paciente con rut: {data["paciente_rut"]}"""
    LogAuditoria.objects.create(tipo="paciente",usuario_id=data["id"],rut=data["rut"], descripcion=log )