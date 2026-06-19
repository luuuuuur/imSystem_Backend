from ims_backend.models import StockInsumo
from ims_backend.toolbox.exceptions import NotFoundException, InternalServerException, BadRequestException
from ims_backend.serializers import UpdateInsumoSerializer
from django.db.models import F
from ims_backend.task_package.task_log_inventario import update_inventario_log
from django.db import transaction
#Update de stock por ambulancias
def update(data, user):
    serializer = UpdateInsumoSerializer(data=data)
    if serializer.is_valid():
        try:
            valid_data = serializer.validated_data
            with transaction.atomic():
                stock = StockInsumo.objects.filter(
                    presentacion_id=valid_data["presentacion_id"],
                    ambulancia_id=valid_data["ambulancia_id"]
                )
                updated = stock.update(stock=F("stock") + valid_data["cantidad"])
                log_data = dict(valid_data)
                log_data["user_id"] = user.id
                log_data["rut"] = user.rut
                transaction.on_commit(lambda:update_inventario_log.delay(data = log_data))
            if updated == 0:
                raise NotFoundException(detail="Presentacion o Ambulancia no encontrada")
            return  updated > 0
        except Exception as e:
            raise InternalServerException(detail=f"Fallo al intentar actualizar los registros: {e}")
    else:
        raise BadRequestException(detail="Los campos no estan siendo nombrados correctamente")
