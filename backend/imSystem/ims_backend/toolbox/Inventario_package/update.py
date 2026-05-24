from ims_backend.models import StockInsumo
from ims_backend.toolbox import exceptions
from ims_backend.toolbox import customencoder
from django.shortcuts import get_object_or_404
from ims_backend.serializers import UpdateInsumoSerializer
from django.db.models import F

#Update de stock por ambulancias
def update(request):
    serializer = UpdateInsumoSerializer(data=request.data)
    if serializer.is_valid():
        try:
            valid_data = serializer.validated_data
            stock = StockInsumo.objects.filter(
                presentacion_id=valid_data["presentacion_id"],
                ambulancia_id=valid_data["ambulancia_id"]
            )
            updated = stock.update(stock=F("stock") + valid_data["cantidad"])
            if updated == 0:
                raise exceptions.NotFoundException(detail="Presentacion o Ambulancia no encontrada")
            return  updated > 0
        except:
            raise exceptions.InternalServerException
    else:
        raise exceptions.BadRequestException
