from ims_backend.models import DeviceToken
from django.db import transaction
from ims_backend.toolbox.exceptions import InternalServerException
def set_device(user_id,token):    
    try:
        with transaction.atomic():
            DeviceToken.objects.update_or_create(
                usuario=user_id,
                defaults={"device_token":token}
            )
        return True
    except:
        raise InternalServerException