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
        data = InsumoMedico.objects.values("id","nombre_insumo","categoria")
        r = []
        for insumo in data: 
            r.append({"insumo":
                {
                "id":insumo["id"],
                "nombre":insumo["nombre_insumo"],
                "categoria":insumo["categoria"]}
                })
        return r
