from celery import shared_task
from ims_backend.models import LogAuditoria, Personal, Ambulancia


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def mover_elemento_log(self,data):
    try:
        user = Personal.objects.get(rut=data["rut"])
        log = f"El usuario con RUT {user.rut} trasladó {data['cantidad']} unidades del insumo con ID {data['presentacion_id']} desde {data['update_from']} hacia {data['update_to']}."
        LogAuditoria.objects.create(tipo="ambulancia",usuario_id=user.id, rut_usuario=user.rut,
                                            descripcion=log)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def agregar_elemento_log(self, data):
    try:
        ids = [str(p) for p in data["added"]]
        log = f"El usuario con RUT {data['rut']} (ID: {data['user']}) agregó los siguientes elementos con IDs: {', '.join(ids)}."
        LogAuditoria.objects.create(
            tipo="ambulancia",usuario_id = data["user"], rut_usuario=data["rut"], descripcion=log
        )
    except Exception as exc:
        raise self.retry(exc=exc)
@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def agregar_ambulancia_log(self, data):
    try:
        user = Personal.objects.get(id=data["user_id"])
        log = f"El usuario con RUT {user.rut} registró la ambulancia con patente {data['patente']}, modelo {data['modelo']} e ID {data['ambulancia_id']}."
        LogAuditoria.objects.create(
            tipo="ambulancia", usuario_id=user.id, rut_usuario=user.rut, descripcion=log
        )
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def actualizar_estados(self, rut, ambid):
    try:
        personal = Personal.objects.get(rut=rut)
        ambulancia = Ambulancia.objects.get(id=ambid)
        log = f"El usuario con RUT {personal.rut} (ID: {personal.id}) actualizó el estado de disponibilidad de la ambulancia con patente {ambulancia.patente} a '{ambulancia.estado_disponibilidad}'."
        LogAuditoria.objects.create(
            tipo="ambulancia", usuario_id = personal.id, rut_usuario= personal.rut, descripcion=log
        )
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def log_senal_otro(self, usuario_id, mensaje):
    try:
        usuario = Personal.objects.get(id=usuario_id)
        log = f"El usuario con RUT {usuario.rut} (ID: {usuario.id}) envió una señal de tipo 'Otro' con el siguiente mensaje: \"{mensaje}\"."
        LogAuditoria.objects.create(
            tipo="ambulancia", usuario_id=usuario.id, rut_usuario=usuario.rut, descripcion=log
        )
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def log_senal_ambulancia(self, usuario_id, patente):
    try:
        usuario = Personal.objects.get(id=usuario_id)
        log = f"El usuario con RUT {usuario.rut} (ID: {usuario.id}) reportó la ambulancia con patente {patente} y la marcó como 'En preparación'."
        LogAuditoria.objects.create(
            tipo="ambulancia", usuario_id=usuario.id, rut_usuario=usuario.rut, descripcion=log
        )
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def log_senal_ocupada(self, usuario_id, patente):
    try:
        usuario = Personal.objects.get(id=usuario_id)
        log = f"El usuario con RUT {usuario.rut} (ID: {usuario.id}) reportó la ambulancia con patente {patente} como 'Actualmente en despacho'."
        LogAuditoria.objects.create(
            tipo="ambulancia", usuario_id=usuario.id, rut_usuario=usuario.rut, descripcion=log
        )
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def log_senal_outofservice(self, usuario_id, patente):
    try:
        usuario = Personal.objects.get(id=usuario_id)
        log = f"El usuario con RUT {usuario.rut} (ID: {usuario.id}) reportó una falla mecánica en la ambulancia con patente {patente} y la marcó como 'Fuera de servicio'."
        LogAuditoria.objects.create(
            tipo="ambulancia", usuario_id=usuario.id, rut_usuario=usuario.rut, descripcion=log
        )
    except Exception as exc:
        raise self.retry(exc=exc)

def _log_senal_equipo(self, usuario_id, grupo_nombre, despacho_id, descripcion):
    try:
        usuario = Personal.objects.get(id=usuario_id)
        LogAuditoria.objects.create(
            tipo="ambulancia", usuario_id=usuario.id, rut_usuario=usuario.rut,
            descripcion=descripcion.format(grupo=grupo_nombre, despacho_id=despacho_id)
        )
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def log_senal_disponible(self, usuario_id, grupo_nombre, despacho_id):
    _log_senal_equipo(self, usuario_id, grupo_nombre, despacho_id, "El Grupo {grupo} notificó que está disponible para un nuevo despacho.")

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def log_senal_en_camino(self, usuario_id, grupo_nombre, despacho_id):
    _log_senal_equipo(self, usuario_id, grupo_nombre, despacho_id, "El Grupo {grupo} notificó que está en camino al destino del despacho: {despacho_id}.")

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def log_senal_en_destino(self, usuario_id, grupo_nombre, despacho_id):
    _log_senal_equipo(self, usuario_id, grupo_nombre, despacho_id, "El Grupo {grupo} notificó que ha llegado al destino del despacho: {despacho_id}.")

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def log_senal_operando(self, usuario_id, grupo_nombre, despacho_id):
    _log_senal_equipo(self, usuario_id, grupo_nombre, despacho_id, "El Grupo {grupo} notificó que ha comenzado a operar en el despacho: {despacho_id}.")

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def log_senal_regresando(self, usuario_id, grupo_nombre, despacho_id):
    _log_senal_equipo(self, usuario_id, grupo_nombre, despacho_id, "El Grupo {grupo} notificó que está regresando a base.")