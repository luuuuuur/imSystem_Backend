from ims_backend.models import SuscritosAGrupo
from ims_backend.serializers import ParamSerializer
from ims_backend.toolbox.exceptions import BadRequestException
from rest_framework.serializers import ValidationError

#Devolver un grupo por ID en query
def with_query(request):
    try:
        serializer = ParamSerializer(data=request.query_params)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            grupos = {}
            suscripciones = SuscritosAGrupo.objects.filter(
                        grupo_id=valid_data['group_id'],fecha_salida=None
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
        else:
            raise ValidationError(detail="Error al procesar el grupo_id, tal vez no es válido?")
    except Exception as e:
         raise BadRequestException(detail=str(e))
