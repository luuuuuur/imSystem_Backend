from ims_backend.models import SuscritosAGrupo, DespachoPersonal
from ims_backend.toolbox.exceptions import NotFoundException

def solicitud_usuario(user):
    suscripciones = SuscritosAGrupo.objects.filter(
        personal=user,
        fecha_salida=None
    ).select_related('grupo')

    if not suscripciones.exists():
        raise NotFoundException(detail="No se encuentra inscrito a ningun grupo")

    grupos = [s.grupo for s in suscripciones]

    despachos = DespachoPersonal.objects.filter(
        grupo__in=grupos
    ).select_related(
        'grupo',
        'despacho',
        'despacho__ambulancia',
        'despacho__creado_por',
        'despacho__atencion',
        'despacho__paciente',
    ).exclude(
        despacho__estado__in=['finalizado', 'cancelado']
    )

    # Pre-fetch members per group to avoid N+1
    personal_por_grupo = {}
    for grupo in grupos:
        personal_por_grupo[grupo.id] = list(
            SuscritosAGrupo.objects.filter(
                grupo=grupo,
                fecha_salida=None
            ).values(
                'personal__id',
                'personal__first_name',
                'personal__last_name',
                'personal__rut',
                'personal__rol__nombre_rol',
            )
        )

    resultado = []
    for dp in despachos:
        d = dp.despacho
        personal = personal_por_grupo.get(dp.grupo_id, [])
        resultado.append({
            'id': str(d.id),
            'estado': d.estado,
            'direccionOrigen': d.direccion_origen,
            'direccionDestino': d.direccion_destino,
            'descripcionLlamado': d.descripcion_llamado,
            'fechaLlamado': d.fecha_llamado,
            'fechaProgramada': d.fecha_programada,
            'paciente': {
                'nombre_completo': d.paciente.nombre_completo,
                'rut': d.paciente.rut,
                'fecha_nacimiento': d.paciente.fecha_nacimiento,
            } if d.paciente else None,
            'ambulancia': {
                'id': str(d.ambulancia.id),
                'patente': d.ambulancia.patente,
                'modelo': d.ambulancia.modelo,
                'estado': d.ambulancia.estado_disponibilidad,
            } if d.ambulancia else None,
            'personalIds': [str(p['personal__id']) for p in personal],
            'personal': personal,
        })

    return resultado
