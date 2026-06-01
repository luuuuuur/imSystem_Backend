from celery import shared_task
from backend.imSystem.ims_backend.models import LogAuditoria, Personal
@shared_task
def agregar_log_atencion(documento):
    user = Personal.objects.get(rut=documento["registrado_por"]["rut"])
    LogAuditoria.objects.create(tipo="atencion",atencion_id=documento["atencion"]["id"],usuario_id=user.id, 
                                rut_usuario=documento["registrado_por"]["rut"],descripcion=
                                f"Registró una atención:{documento["atencion"]["id"]}")