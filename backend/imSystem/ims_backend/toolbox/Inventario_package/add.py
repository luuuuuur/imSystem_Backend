
from backend.imSystem.ims_backend.models import StockInsumo, PresentacionInsumo, InsumoMedico
from ims_backend.serializers import BulkAddInsumoSerializer
from django.db import transaction
from ims_backend.toolbox import exceptions
from ims_backend.task_package.task_log_ambulancias import agregar_elemento_log

#AÑADIR UN STOCK A UNA AMBULANCIA
def add(request):
    serializer = BulkAddInsumoSerializer(data=request.data)
    if serializer.is_valid(raise_exception=True):
        valid_data = serializer.validated_data["items"]
        try:
            with transaction.atomic():
                insumos_arr = InsumoMedico.objects.bulk_create([
                    InsumoMedico(nombre_insumo=data["nombre_insumo"],
                                 categoria_id = data["categoria_id"])
                for data in valid_data])
                presentacin_arr = PresentacionInsumo.objects.bulk_create(
                    [PresentacionInsumo(insumo=insumos_arr[i],
                                        cantidad= data["cantidad"],
                                        unidad_medida_id = data["unidad_medida_id"])
                     for i, data in enumerate(valid_data)])
                StockInsumo.objects.bulk_create([StockInsumo(presentacion = presentacin_arr[i],
                                                             stock = data["stock"],
                                                             ambulancia_id = data["ambulancia_id"])
                
                                                 for i, data in enumerate(valid_data)])
                document ={
                "user": request.user.id,
                "rut": request.user.rut,
                "added":[str(p.id) for p in presentacin_arr]
                }
                transaction.on_commit(lambda:agregar_elemento_log.delay(data=document))
            return True
        except:
            raise exceptions.InternalServerException(detail="Fallo al añadir los registros")
    else:
        raise exceptions.BadRequestException(detail="Typos incorrectos")