from ims_backend.models import DespachoPersonal, Despacho, SuscritosAGrupo
from ims_backend.serializers import ObtenerDespachoSerializer
from ims_backend.toolbox import exceptions
from django.db.models import Prefetch

def all_despachos(query_params=None):
        if query_params:
            serializer = ObtenerDespachoSerializer(data=query_params)
            if serializer.is_valid():
                valid_data = serializer.validated_data
                despacho = Despacho.objects.filter(
                    id=valid_data['despacho_id'],
                ).select_related('ambulancia', 'atencion', 'asignado_por', 'creado_por', 'paciente').prefetch_related(
                    Prefetch('equipo', queryset=DespachoPersonal.objects.select_related('grupo'), to_attr='equipo_prefetch')
                ).exclude(estado__in=['finalizado', 'cancelado']).first()

                if not despacho:
                    raise exceptions.BadRequestException

                dp = despacho.equipo_prefetch[0] if despacho.equipo_prefetch else None
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
                        'rut':despacho.paciente.rut,
                        'fecha_nacimiento':despacho.paciente.fecha_nacimiento if despacho.paciente.fecha_nacimiento else None
                    } if despacho.paciente else None,
                    'personal': personal
                }
                return resultado
            else:
                raise exceptions.NotFoundException(detail="El despacho no fue encontrado")
        else:
            _members_qs = SuscritosAGrupo.objects.filter(
                fecha_salida=None
            ).select_related('personal__rol')

            _equipo_qs = DespachoPersonal.objects.select_related('grupo').prefetch_related(
                Prefetch('grupo__grupo_nombre', queryset=_members_qs, to_attr='miembros_activos')
            )

            despachos = Despacho.objects.exclude(
                    estado__in=['finalizado', 'cancelado']
                ).select_related('ambulancia', 'creado_por', 'asignado_por','atencion','paciente').prefetch_related(
                Prefetch('equipo', queryset=_equipo_qs, to_attr='equipo_prefetch')
            )
            resultado = []
            for d in despachos:
                dp = d.equipo_prefetch[0] if d.equipo_prefetch else None
                personal = []
                if dp:
                    personal = [
                        {
                            'personal__id': m.personal.id,
                            'personal__first_name': m.personal.first_name,
                            'personal__last_name': m.personal.last_name,
                            'personal__rut': m.personal.rut,
                            'personal__rol__nombre_rol': m.personal.rol.nombre_rol if m.personal.rol else None
                        }
                        for m in dp.grupo.miembros_activos
                    ]
                
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