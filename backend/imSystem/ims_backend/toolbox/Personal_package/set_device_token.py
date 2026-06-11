from ims_backend.models import DeviceToken
from django.db import transaction
from ims_backend.toolbox.exceptions import InternalServerException
def set_device(user_id,token):    
    try:
        with transaction.atomic():
            DeviceToken.objects.update_or_create(
                device_token=token,
                defaults={"usuario_id": user_id}
            )
        return True
    except:
        raise InternalServerException