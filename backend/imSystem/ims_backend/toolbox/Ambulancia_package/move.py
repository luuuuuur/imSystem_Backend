from celery.loaders import default

from ims_backend.models import PresentacionInsumo, Ambulancia, StockInsumo
from ims_backend.serializers import MoveItemSerializer
from django.shortcuts import get_object_or_404
from django.db import transaction

from ims_backend.toolbox.exceptions import BadRequestException, InternalServerException, NotFoundException


#Mover item de ambulancia A -> B
def move_item(request):
    serializer = MoveItemSerializer(data=request.data)
    if serializer.is_valid():
        valid_data = serializer.validated_data
        try:
            with transaction.atomic():
                stock_origen = get_object_or_404(StockInsumo.objects.select_for_update(),
                                                 presentacion_id=valid_data["presentacion_id"],
                                                 ambulancia_id=valid_data["ambulancia_from_id"])

                if stock_origen.stock < valid_data["stock"]:
                    raise ConflictException(detail="No hay suficiente stock en el origen")
                stock_destino, _ = StockInsumo.objects.get_or_create(presentacion_id=valid_data["presentacion_id"],
                                                                     ambulancia_id=valid_data["ambulancia_to_id"],
                                                                     defaults={"stock": 0})
                update_from = StockInsumo.objects.filter(id=stock_origen.id).update(stock = F("stock") - valid_data["cantidad"])
                update_to = StockInsumo.objects.filter(id=stock_destino.id).update(stock = F("stock") + valid_data["cantidad"])

                if update_from > 0 and update_to > 0:
                    return True
                else:
                    raise InternalServerException(detail="Fallo al intentar mover la presentacion")
        except (ConflictException, BadRequestException, InternalServerException):
            raise
        except Exception:
            raise NotFoundException(detail="Fallo al intentar encontrar los objetivos")
    else:
        raise BadRequestException(detail="Fallo al mover el item, typos incorrectos")