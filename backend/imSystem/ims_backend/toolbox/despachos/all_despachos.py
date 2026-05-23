from ims_backend.models import *
from ims_backend.serializers import *
from toolbox import exceptions

def all_despachos(request):
        if request.query_params:
            serializer = ObtenerDespachoSerializer(data=request.query_params)
            if serializer.is_valid():
                valid_data = serializer.validated_data
                despacho = Despacho.objects.filter(
                    id=valid_data['despacho_id'],
                ).select_related('ambulancia','atencion','asignado_por','creado_por','paciente').exclude(
                    estado__in=['finalizado', 'cancelado']).first()

                if not despacho:
                    raise exceptions.BadRequestException

                despacho_personal = DespachoPersonal.objects.filter(despacho=despacho).first()
                personal = []
                if despacho_personal:
                    personal = list(SuscritosAGrupo.objects.filter(
                        grupo=despacho_personal.grupo,
                        fecha_salida=None
                    ).values(
                        'personal__id', 'personal__first_name',
                        'personal__last_name', 'personal__rut',
                        'personal__rol__nombre_rol'
                    ))
                resultado = {
                    'id': despacho.id,
                    'estado': despacho.estado,
                    'direccion_origen': despacho.direccion_origen,
                    'direccion_destino': despacho.direccion_destino,
                    'descripcion_llamado': despacho.descripcion_llamado,
                    'fecha_llamado': despacho.fecha_llamado,
                    'fecha_asignacion': despacho.fecha_asignacion,
                    'ambulancia_id': despacho.ambulancia_id,
                    'creado_por_id': despacho.creado_por_id,
                    'asignado_por_id': despacho.asignado_por_id,
                    'paciente':{
                        'nombre_completo': despacho.paciente.nombre_completo,
                        'rut':despacho.paciente.rut
                    } if despacho.paciente else None,
                    'personal': personal
                }
                return resultado
            else:
                raise exceptions.NotFoundException(detail="El despacho no fue encontrado")
        else:
            despachos = Despacho.objects.exclude(
                    estado__in=['finalizado', 'cancelado']
                ).select_related('ambulancia', 'creado_por', 'asignado_por','atencion','paciente')
            resultado = []
            for d in despachos:
                dp = DespachoPersonal.objects.filter(despacho=d).first()
                personal = []
                if dp:
                    personal = list(SuscritosAGrupo.objects.filter(
                        grupo=dp.grupo,
                        fecha_salida=None
                    ).values(
                        'personal__id', 'personal__first_name',
                        'personal__last_name', 'personal__rut',
                        'personal__rol__nombre_rol'
                    ))
                
                resultado.append({
                    'id': d.id,
                    'estado': d.estado,
                    'direccion_origen': d.direccion_origen,
                    'direccion_destino': d.direccion_destino,
                    'descripcion_llamado': d.descripcion_llamado,
                    'fecha_llamado': d.fecha_llamado,
                    'fecha_asignacion': d.fecha_asignacion,
                    'ambulancia_id': d.ambulancia_id,
                    'paciente':{
                        'nombre_completo':d.paciente.nombre_completo,
                        'rut':d.paciente.rut
                    } if d.paciente else None,
                    'personal': personal
                })

            return resultado