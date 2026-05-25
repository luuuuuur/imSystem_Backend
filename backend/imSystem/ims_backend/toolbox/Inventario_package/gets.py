from ims_backend.serializers import InsumoIdSerializer
from ims_backend.toolbox import exceptions
from ims_backend.toolbox.Inventario_package import inventario


def get_perid(request):
    if request.query_params:
        serializer = InsumoIdSerializer(data=request.query_params)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            r = inventario.specific(valid_data)
            return r
        else:
            raise exceptions.BadRequestException
    else:
        return exceptions.UnAuthorizedException
def get_all():
    try:
        r = inventario.all()
        return r
    except:
        raise exceptions.InternalServerException