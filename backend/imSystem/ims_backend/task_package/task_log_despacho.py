from ims_backend.models import LogAuditoria
from celery import shared_task

@shared_task
def crear_despacho_log(data):
    log = f"""El usuario con rut: {data["rut"]} y id: {data["user_id"]}. Creó un despacho con id: {data["id"]} para el paciente con rut: {data["paciente_rut"]}"""
    LogAuditoria.objects.create(tipo='despacho', usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)


@shared_task
def asignar_despacho_log(data):
    log = f"""El usuario con rut: {data["rut"]} y id: {data["user_id"]}. 
    Asignó un despacho con id: {data["id"]} para el grupo con nombre: {data["nombre_grupo"]} y id: {data["grupo_id"]} y la ambulancia: {data["patente"]}"""
    LogAuditoria.objects.create(tipo='despacho', usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
