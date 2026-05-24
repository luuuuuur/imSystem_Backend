from ims_backend.models import *
from django.shortcuts import get_object_or_404
from ims_backend.toolbox import exceptions
def specific(valid_data):
    try:
        stocks = StockInsumo.objects.select_related(
            'ambulancia',
            'presentacion__insumo__categoria',
            'presentacion__unidad_medida'
        ).filter(ambulancia_id=valid_data["ambulancia_id"])
        r =[]

        for data in stocks:
            r.append({
                "ambulancia":{
                    "id":data.ambulancia.id,
                    "patente":data.ambulancia.patente,
                    "estado":data.ambulancia.estado_disponibilidad,
                    "stock":[{
                        "insumo_nombre":data.presentacion.insumo.nombre_insumo,
                        "categoria":data.presentacion.insumo.categoria.categoria,
                        "unidad_medida":data.presentacion.unidad_medida.unit,
                        "stock":data.stock
                    }]
                }
            })
        return r
    except:
        raise exceptions.NotFoundException


def all():
    try:
        stocks = StockInsumo.objects.select_related(
            'ambulancia',
            'presentacion__insumo__categoria',
            'presentacion__unidad_medida'
        ).all()
        r =[]

        for data in stocks:
            r.append({
                "ambulancia":{
                    "id":data.ambulancia.id,
                    "patente":data.ambulancia.patente,
                    "estado":data.ambulancia.estado_disponibilidad,
                    "stock":[{
                        "insumo_nombre":data.presentacion.insumo.nombre_insumo,
                        "categoria":data.presentacion.insumo.categoria.categoria,
                        "unidad_medida":data.presentacion.unidad_medida.unit,
                        "stock":data.stock
                    }]
                }
            })
        return r
    except:
        raise exceptions.InternalServerException