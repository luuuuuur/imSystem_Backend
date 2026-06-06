from ims_backend.models import Despacho
from django.utils import timezone

def change_despacho_status(type, despacho: Despacho,fecha_prog=None):
    match type:
        case Despacho.ASIGNADO:
                despacho.fecha_asignacion = timezone.now()
                despacho.estado = Despacho.ASIGNADO
                despacho.save(update_fields=["estado", "fecha_asignacion"])
        case Despacho.FINALIZADO:
                despacho.fecha_finalizacion = timezone.now()
                despacho.estado = Despacho.FINALIZADO
                despacho.save(update_fields=["estado", "fecha_finalizacion"])
        case Despacho.CANCELADO:
                despacho.fecha_finalizacion = timezone.now()
                despacho.estado = Despacho.CANCELADO
                despacho.save(update_fields=["estado","fecha_finalizacion"])
        case Despacho.PROGRAMADO:
                despacho.fecha_programada = fecha_prog
                despacho.estado = Despacho.PROGRAMADO
                despacho.save(update_fields=["estado","fecha_programada"])
        case _:
            return