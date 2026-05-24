from django.http import Http404
from ims_backend.models import *
from django.shortcuts import get_object_or_404
from django.forms.models import model_to_dict
from ims_backend.serializers import InsumoIdSerializer
from ims_backend.toolbox import exceptions
from ims_backend.toolbox.Inventario import inventario
def get_perid(request):
    if request.query_params:
        serializer = InsumoIdSerializer(data=request.query_params)
        if serializer.is_valid():
            valid_data = serializer.validate_data
            r = inventario.specific(valid_data)
            return r
        else:
            raise exceptions.BadRequestException
    else:
        exceptions.UnAuthorizedException