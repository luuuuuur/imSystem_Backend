from ims_backend.models import *
from ims_backend.toolbox import exceptions
from ims_backend.serializers import AmbulanciaSerializerID
from ims_backend.toolbox.Ambulancias import inventario
def get_perid(request):
    if request.query_params:
        serializer = AmbulanciaSerializerID(data=request.query_params)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            r = inventario.specific(valid_data)
            return r
        else:
            raise exceptions.NotFoundException
    else:
        raise exceptions.BadRequestException
    
def get_all():
    try:
        r = inventario.all()
        return r
    except:
        raise exceptions.InternalServerException