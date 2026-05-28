from celery import shared_task
from ims_backend.models import LogAuditoria, Personal


@shared_task
def mover_elemento_log(data):
    user = Personal.objects.get(rut=data["rut"])
    log = f"""El usuario con rut: {user.rut}, movió desde {data["update_from"]} -> {data["update_to"]}, el insumo con id: 
    {data["presentacion_id"]} la cantidad de: {data["cantidad"]}
    """
    LogAuditoria.objects.create(tipo="ambulancia",usuario_id=user.id, rut_usuario=user.rut,
                                           descripcion=log)


@shared_task
def agregar_elemento_log(data):
    ids = [str(p) for p in data["added"]]
    log = f"""El usuario con id: {data["user"]} y rut: {data["rut"]}, agregó los siguientes elementos
    con ids: {','.join(ids)}"""
    LogAuditoria.objects.create(
        tipo="ambulancia",usuario_id = data["user"], rut_usuario=data["rut"], descripcion=log
    )