from ims_backend.models import LogAuditoria
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def crear_grupo_log(self, data):
    try:
        ruts = [str(p) for p in data["personal"]]
        log = f"""El usuario con id: {data["user_id"]} y rut: {data["rut"]}. A creado el grupo con nombre: {data["nombre_grupo"]}, y ha asignado a este grupo los siguientes ruts: {','.join(ruts)}"""
        LogAuditoria.objects.create(tipo="grupo", usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def agregar_miembros_log(self, data):
    try:
        log = f"""El usuario con id: {data["user_id"]} y rut: {data["rut"]}. A agregado al miembro con rut: {data["personal_rut"]} al grupo con id: {data["group_id"]} con nombre: {data["group_nombre"]}"""
        LogAuditoria.objects.create(tipo="grupo", usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def actualizar_estado_miembros_log(self, data):
    try:
        log = f"""El usuario con id: {data["user_id"]} y rut: {data["rut"]}. A desacoplado al usuario con rut: {data["personal_rut"]} del grupo con id: {data["group_id"]} y nombre: {data["group_name"]}"""
        LogAuditoria.objects.create(tipo="grupo", usuario_id=data["user_id"], rut_usuario=data["rut"], descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)