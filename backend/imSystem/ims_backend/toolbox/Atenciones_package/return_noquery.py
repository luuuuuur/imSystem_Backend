from ims_backend.models import Atencion
from ims_backend.toolbox.exceptions import InternalServerException

def atencion_noquery():
    try:
        atencion = Atencion.objects.select_related('despacho__paciente').order_by('-id').iterator(chunk_size=100)
        response = []
        for a in atencion:
            response.append({
                    'atencion_id': a.id,
                    'hora_salida':a.hora_salida,
                    'hora_llegada':a.hora_llegada,
                    'estado_sello':a.estado_sello,
                    'firma_digital': a.sello_electronico,
                    'despacho':{
                        'despacho_id':a.despacho.id,
                        'paciente':{
                            'nombre':a.despacho.paciente.nombre_completo,
                            'rut':a.despacho.paciente.rut
                        } if a.despacho.paciente else None,
                    }if a.despacho else None
            })
        return response
    except Exception as e:
        raise InternalServerException(detail=str(e))