#---DJANGO REST FRAMEWORK IMPORTS-----
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.permissions import AllowAny
#---DJANGO IMPORTS---
from django.contrib.auth import authenticate, login
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.forms.models import model_to_dict
#---PYTHON INCLUDES IMPORTS---
import hashlib
import json

#---PERSONAL MODULES IMPORTS---
from load_key import GLOBAL_PRIVATE_KEY
from . import utils
#---MODELS IMPORTS---
from .models import Personal
from .models import Paciente
from .models import SuscritosAGrupo
from .models import GrupoPersonal
from .models import RolPersonal
from .models import Despacho
from .models import Ambulancia
from .models import DespachoPersonal
# Create your views here.
#----CLASS BASED VIEWS----
# Permiso custom: restringe acceso a usuarios con rol control
# Usar en vistas donde solo personal de control debe operar (como por ejemplo asignar trabajores, despachos etc)
class ControlProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol.nombre_rol == 'control'
class MedicProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol.nombre_rol == 'medic'     
class NurseProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol.nombre_rol == 'nurse'

class Login(APIView):
    #TODO: Implementacion de MFA con Google Authenticator (TOTP)
    permission_classes = []
    def post(self, request):
        data_user = request.data.get('username')
        data_pass = request.data.get('password')

        try:
            user = authenticate (
                request,
                username = data_user,
                password = data_pass
            )
            if user is None:
                return Response(
                {'error':'Fallo al cargar al usuario, estás seguro de haber ingresado las credenciales correctas?'}
                ,status=status.HTTP_401_UNAUTHORIZED)
            login(request,user)
            #TODO: obtener el rol del usuario para retornarlo dentro del json
            return Response({'success':'success', 'role': user.rol.nombre_rol}, status=status.HTTP_200_OK)
        except ValueError as v:
            return Response({'error':str(v)}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'error':'Fallo interno: ' + str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




#TODO: Creacion de la api para cargar y actualizar datos del inventario
class Inventory(APIView):
    permission_classes  = [ControlProfileOnly]





#TODO: API para obtener datos del personal
class DataPersonal(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return[AllowAny()]
        return [ControlProfileOnly()]
    def get(self, request):
        data_personal = Personal.objects.filter(is_active=True).values(
            'id', 'first_name', 'last_name', 'rut', 'rol__nombre_rol','is_active')
        return Response(list(data_personal), status=status.HTTP_200_OK)
    def post(self, request):
        data = request.data
        try:
            key,totp= utils.generate_totp()
            temp = utils.generate_password()
            rol = get_object_or_404(RolPersonal, id=data.get("rol_id"))
            uri = totp.provisioning_uri(name=data.get('rut'), issuer_name='IMS Sistema')
            Personal.objects.create_user(username=data.get("rut"),
                                         first_name=data.get("first_name"),
                                         last_name=data.get("last_name"),
                                         password=temp,
                                         totp_secret =key,
                                         rut=data.get("rut"),
                                         rol=rol)
            return Response({'success':'success', 'totp_uri':uri, 'password':temp}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error':str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#TODO: Creacion de la validación del TOTP (MFA)
#TODO: Creación de la API de notificaciones -> SSE
#TODO: Creación de la API para carga de documentos y descarga de documentos (SOLO lectura, generar un QR desde HASH) -> prioridad
#AUN NO FUNCIONA
#TODO: Creación de la API para la modificación de los documentos
class DocumentsAPI(APIView):
    def post(self,request):
        data = request.data
        try:
            converted_data = json.dumps(data,sort_keys=True, ensure_ascii=False)
            sha_256 = hashlib.sha256(converted_data.encode('utf-8')).hexdigest()
            sign = GLOBAL_PRIVATE_KEY.sign(bytes.fromhex(sha_256))
            data["Hash"] = str(sha_256)
            data["Firma"] = str(sign.hex())
            #TODO: Preparar json para subir a S3
            return Response({'success':'success'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


#TODO: Creación de la API para la gestión de los Equipos de trabajo
class Grupos(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return[AllowAny()]
        return [ControlProfileOnly()]
    def post(self, request):
        data = request.data
        try:
            with transaction.atomic():
                grupo = GrupoPersonal.objects.create(nombre_grupo= data.get('nombre_grupo'))
                for p_fk in data.get('personal', []):
                    persona = Personal.objects.get(id=p_fk)
                    SuscritosAGrupo.objects.create(grupo=grupo, personal=persona)
            return Response({'success':'success'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error':'failed to create group: '+str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    def patch(self, request):
        data = request.data
        try:
            persona = get_object_or_404(Personal, id=data.get('p_id'))
            grupo_to_update = get_object_or_404(GrupoPersonal,id=data.get('group_id'))
            with transaction.atomic():
                SuscritosAGrupo.objects.filter(
                    grupo=grupo_to_update,
                    personal=persona,
                    fecha_salida=None
                ).update(
                    fecha_salida=timezone.now()
                )
            return Response({'success':'success'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error':'failed to update the group: '+str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    def get(self, request):
        data = request.data
        query = SuscritosAGrupo.objects.filter(grupo_id=data.get('grupo_id'), fecha_salida=None).values(
            'personal__id', 'personal__first_name','personal__last_name','personal__rut','personal__rol__nombre_rol'
        )

        return Response(list(query), status=status.HTTP_200_OK)
class AddMemberToGroup(APIView):
    permission_classes = [ControlProfileOnly]
    def post(self, request):
        data = request.data
        try:
            persona = get_object_or_404(Personal, id=data.get('p_id'))
            grupo_to_update = get_object_or_404(GrupoPersonal, id=data.get('group_id'))
            with transaction.atomic():
                SuscritosAGrupo.objects.create(grupo=grupo_to_update, 
                                               personal=persona, 
                                               fecha_salida=None)
            return Response({'success':'success'}, status=status.HTTP_201_CREATED)
        except Exception as ta:
            return Response({'error':str(ta)}, status=status.HTTP_400_BAD_REQUEST)

#TODO:Creacion de la API para el registro de los pacientes
class RegistrosPacientesAPI(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return[AllowAny()]
        return [ControlProfileOnly()]

    def post(self, request):
        data = request.data
        try:
            Paciente.objects.create(rut=data.get('rut'),
            nombre_completo=data.get('full_name'), fecha_nacimiento=data.get('date_birth'),
            direccion=data.get('direccion'), condicion_paciente=data.get('condicion_paciente'),
            telefono=data.get('telefono'), comuna=data.get('comuna'))
            return Response({'success':'success'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error':str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    def get(self, request):
        data = request.data
        if 'id' in data:
            try:
                paciente = get_object_or_404(Paciente,id=data.get('id'))
                return Response(model_to_dict(paciente)
                                , status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error':str(e)}, status=status.HTTP_200_OK)
        else:
            pacientes = Paciente.objects.all().values(
                'id', 'rut', 'nombre_completo', 'fecha_nacimiento',
                'direccion', 'condicion_paciente', 'telefono', 'comuna'
            )
            return Response(list(pacientes), status=status.HTTP_200_OK)

#TODO: Creación de la API para los estados de los usuarios (en turno, disponible, fuera de servicio)
#TODO: Creación de la API para la gestión de los datos de los pacientes(para cargar al documento)
#TODO: Creacion de la API para despachar las atenciones
class CreateDespacho(APIView):
    permission_classes = [ControlProfileOnly]
    def post(self, request):
        data = request.data
        try:
            with transaction.atomic():
                Despacho.objects.create( direccion_origen=data.get('d_o'),
                direccion_destino=data.get('d_d'),descripcion_llamado=data.get('d_llamado'),
                creado_por=request.user,estado='recibido')
            return Response({'success':'success'}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error':str(e)}, status=status.HTTP_400_BAD_REQUEST)
class AsignarDespacho(APIView):
    permission_classes = [ControlProfileOnly]
    def patch(self, request):
        data = request.data
        try:
            amb = get_object_or_404(Ambulancia, id=data.get('amb_id'))
            with transaction.atomic():
                Despacho.objects.filter(id=data.get('d_id')).update(
                    fecha_asignacion=timezone.now(),asignado_por=request.user,
                    ambulancia=amb, estado='asignado')
                despacho=get_object_or_404(Despacho, id=data.get('d_id'))
                grupo_asign=get_object_or_404(GrupoPersonal, id=data.get('group_id'))
                DespachoPersonal.objects.create(despacho=despacho, grupo=grupo_asign)
                return Response({'success':'success'},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error':str(e)}, status=status.HTTP_400_BAD_REQUEST)
#TODO: Creacion de la API de logs para Auditorías -> para debatir
#TODO: Creación de la API de exportación de las atenciones en formatio FHIR HL7
#TODO: Creación de la API de tickets para recuperación de credenciales