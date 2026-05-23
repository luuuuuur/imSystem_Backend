from ims_backend.models import *
from ims_backend.serializers import InsumoIdSerializer
from ims_backend.toolbox.Inventario.get_query import get_query
from ims_backend.toolbox import exceptions
def evaluate(request):
    if request.query_params:
        serializer = InsumoIdSerializer(data=request.query_params)
        if serializer.is_valid():
            valid_data = serializer.validate_data
            r = get_query(valid_data)
            return r
        else:
            raise exceptions.BadRequestException
    else:
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
