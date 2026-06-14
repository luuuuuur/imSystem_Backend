from ims_backend.models import Atencion, SuscritosAGrupo, DespachoPersonal
from ims_backend.toolbox.exceptions import InternalServerException, NotFoundException, ForbiddenException
from rest_framework.serializers import ValidationError
from ims_backend.serializers import ParamAtencionSerializer
from django.shortcuts import get_object_or_404
from ims_backend.utils import get_s3_download_url
from botocore.exceptions import ClientError

def atencion_with_query(request):
    serializer = ParamAtencionSerializer(data=request.query_params)
    if serializer.is_valid():
        valid_data=serializer.validated_data
        try:
            atencion = get_object_or_404(Atencion, id=valid_data['id'])

            if request.user.rol.nombre_rol != 'control':
                user_groups = SuscritosAGrupo.objects.filter(
                    personal=request.user
                ).values_list('grupo_id', flat=True)

                if not atencion.despacho or not DespachoPersonal.objects.filter(
                    despacho=atencion.despacho,
                    grupo_id__in=user_groups
                ).exists():
                    raise ForbiddenException(detail="No tienes acceso a esta atención")

            document = atencion.documentos.first()
            if not document:
                raise NotFoundException(detail="No se encontró la atencion")
            url = get_s3_download_url(document.archivo_s3_key, 3600)
            return url
        except ClientError:
            raise InternalServerException(detail="No se logró generar la URL de descarga")
    else:
        raise ValidationError(detail="Estas seguro de haber puesto un ID válido?")