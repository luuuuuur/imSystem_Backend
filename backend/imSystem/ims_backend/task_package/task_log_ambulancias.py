from celery import shared_task
from ims_backend.models import LogAuditoria, Personal, Ambulancia


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def mover_elemento_log(self,data):
    try:
        user = Personal.objects.get(rut=data["rut"])
        log = f"""El usuario con rut: {user.rut}, movió desde {data["update_from"]} -> {data["update_to"]}, el insumo con id: 
        {data["presentacion_id"]} la cantidad de: {data["cantidad"]}
        """
        LogAuditoria.objects.create(tipo="ambulancia",usuario_id=user.id, rut_usuario=user.rut,
                                            descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def agregar_elemento_log(self, data):
    try:
        ids = [str(p) for p in data["added"]]
        log = f"""El usuario con id: {data["user"]} y rut: {data["rut"]}, agregó los siguientes elementos
        con ids: {','.join(ids)}"""
        LogAuditoria.objects.create(
            tipo="ambulancia",usuario_id = data["user"], rut_usuario=data["rut"], descripcion=log
        )
    except Exception as exc:
        raise self.retry(exc=exc)
@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def actualizar_estados(self, conid, ambid):
    try:
        personal = Personal.objects.get(id = conid)
        ambulancia = Ambulancia.objects.get(ambid)
        log = f"El usuario: {personal.id} actualizó el estado de la ambulancia: {ambulancia.patente} a -> {ambulancia.estado_disponibilidad}"
        LogAuditoria.objects.create(
            tipo="ambulancia", usuario_id = personal.id, rut_usuario= personal.rut, descripcion=log
        )
    except Exception as exc:
        raise self.retry(exc=exc)