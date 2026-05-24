from ims_backend.models import *
from django.shortcuts import get_object_or_404
from ims_backend.serializers import InsumoIdSerializer
from ims_backend.toolbox import exceptions
def specific(valid_data):
    try:
        stock = get_object_or_404(StockInsumo.objects.select_related("presentacion__insumo__categoria", "ambulancia",
                                                                     "presentacion__unidad_medida"),
                presentacion__insumo_id=valid_data["insumo_id"])
        r = {
            "insumo":{
                "id":stock.presentacion.insumo.id,
                "nombre": stock.presentacion.insumo.nombre_insumo,
                "categoria": stock.presentacion.insumo.categoria.categoria,
                "categoria_id": stock.presentacion.insumo.categoria.id,
                "unidad_medida":stock.presentacion.unidad_medida.unit,
                "ambulancia":{
                    "patente":stock.ambulancia.patente,
                    "stock":stock.stock,
                }
            }
        }
        return r
    except:
        raise exceptions.NotFoundException



def all():
    try:
        presentacion = StockInsumo.objects.select_related('presentacion__insumo__categoria', 'presentacion__unidad_medida', 'ambulancia').all()
        r = []
        for data in presentacion:
            r.append({
                "id":data.id,
                "insumo":{
                    "insumo_id":data.presentacion.insumo.id,
                    "nombre":data.presentacion.insumo.nombre_insumo,
                    "categoria":data.presentacion.insumo.categoria.categoria,
                    "categoria_id":data.presentacion.insumo.categoria.id,
                    "unidad_medida":data.presentacion.unidad_medida.unit,
                },
                "ambulancia":{
                    "patente":data.ambulancia.patente,
                    "stock":data.stock
                }
            })
        return r
    except:
        raise exceptions.InternalServerException
