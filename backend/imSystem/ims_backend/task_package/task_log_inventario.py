from ims_backend.models import LogAuditoria
from celery import shared_task


@shared_task
def update_inventario_log(data):
    log = f"""El usuario con id: {data["user_id"]}, y rut: {data["rut"]}. A actualizado en la ambulancia con id: {data["ambulancia_id"]},
    el stock de la presentacion con id: {data["presentacion_id"]}, la cantidad de: {data["cantidad"]}"""
    LogAuditoria.objects.create(
        tipo="inventario",usuario_id = data["user_id"], rut_usuario = data["rut"],descripcion=log
    )
