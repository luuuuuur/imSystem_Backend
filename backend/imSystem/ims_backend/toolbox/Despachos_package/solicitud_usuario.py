from ims_backend.models import SuscritosAGrupo,DespachoPersonal
from ims_backend.toolbox.exceptions import NotFoundException, InternalServerException
def solicitud_usuario(request):
        try:
            # buscar el grupo activo del usuario
            suscripcion = SuscritosAGrupo.objects.filter(
                personal=request.user,
                fecha_salida=None
            ).first()

            if not suscripcion:
                raise NotFoundException(detail="No se encuentra inscrito a ningun grupo")

            # buscar despachos asignados a ese grupo
            despachos = DespachoPersonal.objects.filter(
                grupo=suscripcion.grupo
            ).select_related(
                'despacho',
                'despacho__ambulancia',
                'despacho__creado_por',
                'despacho__atencion',
            ).exclude(
                despacho__estado__in=['finalizado', 'cancelado']
            )
            personal = SuscritosAGrupo.objects.filter(
                    grupo=suscripcion.grupo,
                    fecha_salida=None
                ).values(
                    'personal__id',
                    'personal__first_name',
                    'personal__last_name',
                    'personal__rut',
                    'personal__rol__nombre_rol',
            )
            
            resultado = []
            for dp in despachos:
                d = dp.despacho
                # obtener personal del grupo
                resultado.append({
                    'id': str(d.id),
                    'estado': d.estado,
                    'direccionOrigen': d.direccion_origen,
                    'direccionDestino': d.direccion_destino,
                    'descripcionLlamado': d.descripcion_llamado,
                    'fechaLlamado': d.fecha_llamado,
                    'paciente':{
                        'nombre_completo':d.paciente.nombre_completo,
                        'rut':d.paciente.rut
                    } if d.paciente else None,
                    'ambulancia': {
                        'id': str(d.ambulancia.id),
                        'patente': d.ambulancia.patente,
                        'modelo': d.ambulancia.modelo,
                        'estado': d.ambulancia.estado_disponibilidad,
                    } if d.ambulancia else None,
                    'personalIds': [str(p['personal__id']) for p in personal],
                    'personal': list(personal),
                })

            return resultado
        except Exception:
            return InternalServerException(detail="Fallo al obtener los datos")