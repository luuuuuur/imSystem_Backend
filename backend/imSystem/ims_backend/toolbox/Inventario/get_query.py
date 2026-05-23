from django.http import Http404

from ims_backend.models import *
from django.shortcuts import get_object_or_404
from django.forms.models import model_to_dict
from ims_backend.serializers import InsumoIdSerializer
from ims_backend.toolbox import exceptions
def get_query(valid_data: InsumoIdSerializer):
    try:
        insumo = get_object_or_404(InsumoMedico, id=valid_data["id"])

        r = {
            "insumo":{
                "id":insumo.id,
                "nombre": insumo.nombre_insumo,
                "categoria": insumo.categoria
            }
        }
        return r
    except:
        raise exceptions.NotFoundException