from ims_backend.models import StockInsumo
from ims_backend.toolbox import exceptions
def specific(valid_data):
    try:
        stocks = StockInsumo.objects.select_related(
            'ambulancia',
            'presentacion__insumo__categoria',
            'presentacion__unidad_medida'
        ).filter(ambulancia_id=valid_data["ambulancia_id"])
        r ={}
        for data in stocks:
            amb_id = data.ambulancia.id
            if amb_id not in r:
                r[amb_id] = {
                    "ambulancia_id": data.ambulancia.id,
                    "patente": data.ambulancia.patente,
                    "estado": data.ambulancia.estado_disponibilidad,
                    "stock": []
                }
            r[amb_id]["stock"].append({
                "presentacion_id":data.presentacion.insumo.id,
                "insumo_nombre": data.presentacion.insumo.nombre_insumo,
                "insumo_cantidad":data.presentacion.cantidad,
                "categoria": data.presentacion.insumo.categoria.categoria,
                "unidad_medida": data.presentacion.unidad_medida.unit,
                "stock": data.stock
            })
        return list(r.values())
    except Exception as e:
        raise exceptions.NotFoundException(detail=str(e))


def all():
    try:
        stocks = StockInsumo.objects.select_related(
            'ambulancia',
            'presentacion__insumo__categoria',
            'presentacion__unidad_medida'
        ).all()
        r ={}
        for data in stocks:
            amb_id = data.ambulancia.id
            if amb_id not in r:
                r[amb_id] = {
                    "ambulancia_id":data.ambulancia.id,
                    "patente": data.ambulancia.patente,
                    "estado": data.ambulancia.estado_disponibilidad,
                    "stock": []
                }
            r[amb_id]["stock"].append({
                "presentacion_id":data.presentacion.insumo.id,
                "insumo_nombre": data.presentacion.insumo.nombre_insumo,
                "insumo_cantidad":data.presentacion.cantidad,
                "categoria": data.presentacion.insumo.categoria.categoria,
                "unidad_medida": data.presentacion.unidad_medida.unit,
                "stock": data.stock
            })
        return list(r.values())
    except Exception as e:
        raise exceptions.InternalServerException(detail=str(e))