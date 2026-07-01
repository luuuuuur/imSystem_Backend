from ims_backend.models import StockInsumo, Ambulancia
from ims_backend.toolbox import exceptions
from django.db.models import Prefetch
def specific(valid_data):
    try:
        ambulancias = Ambulancia.objects.prefetch_related(
            Prefetch(
                'stocks_ambulancia',
                queryset=StockInsumo.objects.select_related(
                    'presentacion__insumo__categoria',
                    'presentacion__unidad_medida'
                ),
                to_attr='lista_stocks'
            )
        ).filter(id=valid_data["ambulancia_id"])

        r = {}
        for amb in ambulancias:
            amb_id = amb.id
            r[amb_id] = {
                "ambulancia_id": amb.id,
                "patente": amb.patente,
                "estado": amb.estado_disponibilidad,
                "stock": []
            }
            for stock_item in amb.lista_stocks:
                r[amb_id]["stock"].append({
                    "presentacion_id": stock_item.presentacion.insumo.id,
                    "insumo_nombre": stock_item.presentacion.insumo.nombre_insumo,
                    "insumo_cantidad": stock_item.presentacion.cantidad,
                    "categoria": stock_item.presentacion.insumo.categoria.categoria,
                    "unidad_medida": stock_item.presentacion.unidad_medida.unit,
                    "stock": stock_item.stock
                })
        return list(r.values())
    except Exception as e:
        raise exceptions.NotFoundException(detail=str(e))


def all():
    try:
        ambulancias = Ambulancia.objects.prefetch_related(
            Prefetch(
                'stocks_ambulancia',
                queryset=StockInsumo.objects.select_related(
                    'presentacion__insumo__categoria',
                    'presentacion__unidad_medida'
                ),
                to_attr='lista_stocks'
            )
        ).all()
        r ={}
        for amb in ambulancias:
            amb_id = amb.id
            
            r[amb_id] = {
                "ambulancia_id": amb.id,
                "patente": amb.patente,
                "estado": amb.estado_disponibilidad,
                "stock": []
            }
            for stock_item in amb.lista_stocks:
                r[amb_id]["stock"].append({
                    "presentacion_id": stock_item.presentacion.insumo.id,
                    "insumo_nombre": stock_item.presentacion.insumo.nombre_insumo,
                    "insumo_cantidad": stock_item.presentacion.cantidad,
                    "categoria": stock_item.presentacion.insumo.categoria.categoria,
                    "unidad_medida": stock_item.presentacion.unidad_medida.unit,
                    "stock": stock_item.stock
                })
        return list(r.values())
    except Exception as e:
        raise exceptions.InternalServerException(detail=str(e))