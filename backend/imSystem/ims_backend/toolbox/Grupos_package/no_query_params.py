from ims_backend.models import SuscritosAGrupo
from ims_backend.toolbox.exceptions import InternalServerException
#Todos los miembros ordenados por grupo
def no_query_params():
    try:
        grupos = {}
        suscripciones = SuscritosAGrupo.objects.filter(
                    fecha_salida=None
                ).select_related('grupo', 'personal', 'personal__rol')
        for suscripcion in suscripciones:
            grupo_id = suscripcion.grupo.id
            if grupo_id not in grupos:
                grupos[grupo_id] = {
                            'grupo_id': grupo_id,
                            'grupo_nombre': suscripcion.grupo.nombre_grupo,
                            'miembros': []
                }
            grupos[grupo_id]['miembros'].append({
                        'nombre': suscripcion.personal.full_name,
                        'rut': suscripcion.personal.rut,
                        'rol': suscripcion.personal.rol.nombre_rol if suscripcion.personal.rol else None,
                        'dia_ingresado': suscripcion.fecha_entrada,
                        'dia_salida': suscripcion.fecha_salida
                    })
            r = list(grupos.values())
        return r
    except:
        raise InternalServerException