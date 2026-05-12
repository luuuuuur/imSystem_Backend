#---DJANGO REST FRAMEWORK IMPORTS-----
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.permissions import AllowAny
#---DJANGO IMPORTS---
from django.contrib.auth import authenticate, login
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
#---PYTHON INCLUDES IMPORTS---
import hashlib
import json
#---SERIALIZERS---
from .serializers import PersonalSerializer
from .serializers import CrearGrupoSerializer
from .serializers import RemoverMiembroGrupo
from .serializers import AgregarMiembroGrupo
from .serializers import PacienteSerializer
from .serializers import DespachoSerializer
from .serializers import AsignarDespachoSerializer
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
from .models import Atencion

#---CLASS PERMISSION BASED---
# Permiso custom: restringe acceso a usuarios con rol control
# Usar en vistas donde solo personal de control debe operar (como por ejemplo asignar trabajores, despachos etc)
class ControlProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol.nombre_rol == 'control')
class MedicProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol.nombre_rol == 'medic')    
class NurseProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol.nombre_rol == 'nurse')
    
class DriverProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol.nombre_rol == 'driver')

class WorkerProfileOnly(BasePermission):
    def has_permission(self, request,views):
        return bool(request.user.is_authenticated and request.user.rol.nombre_rol in ['medic', 'nurse', 'driver'])


#--CSRF TOKEN METHOD CLASS---
class EnsureCsrfMixin:
    @method_decorator(ensure_csrf_cookie)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
#----CLASS BASED VIEWS----
class Login(EnsureCsrfMixin, APIView):
    #TODO: Implementacion de MFA con Google Authenticator (TOTP)
    permission_classes = [AllowAny]
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
        except ValueError:
            return Response({'error':'wrong values check again'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception:
            return Response({'error':'inner error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




#TODO: Creacion de la api para cargar y actualizar datos del inventario
class Inventory(APIView):
    permission_classes  = [ControlProfileOnly]



#TODO: API de las ambulancias
class AmbulanciaAPI(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [ControlProfileOnly()]
    

    def get(self, request):
        data_ambulancias = Ambulancia.objects.all().values('id', 'patente','modelo','estado_disponibilidad')
        return Response(list(data_ambulancias), status=status.HTTP_200_OK)


#TODO: API para obtener datos del personal
class DataPersonal(APIView):
    def get_permissions(self):
        # Paréntesis agregados para instanciar las clases correctamente
        if self.request.method == 'GET':
            return [WorkerProfileOnly()]
        return [ControlProfileOnly()]

    def get(self, request):
        personal_activo = Personal.objects.filter(is_active=True)
        

        serializer = PersonalSerializer(personal_activo, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = PersonalSerializer(data=request.data)

        if serializer.is_valid():
            try:

                valid_data = serializer.validated_data
                
                rut = valid_data.get('rut')
                first_name = valid_data.get('first_name')
                last_name = valid_data.get('last_name')
                

                rol_id = request.data.get("rol_id")
                rol = get_object_or_404(RolPersonal, id=rol_id)

                key, totp = utils.generate_totp()
                temp = utils.generate_password()
                uri = totp.provisioning_uri(name=rut, issuer_name='IMS Sistema')
                
               
                usuario = Personal.objects.create_user(
                    username=rut,
                    first_name=first_name,
                    last_name=last_name,
                    password=temp,
                    totp_secret=key,
                    rut=rut,
                    rol=rol
                )
                
                return Response({
                    'success': 'success', 
                    'totp_uri': uri, 
                    'password': temp,
                    'usuario_id': usuario.id
                }, status=status.HTTP_201_CREATED)
                
            except Exception:
                return Response({'error': 'failed to generate the uri and user data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#TODO: Creacion de la validación del TOTP (MFA)
#TODO: Creación de la API de notificaciones -> SSE
#TODO: Creación de la API para carga de documentos y descarga de documentos (SOLO lectura, generar un QR desde HASH) -> prioridad
class DocumentsAPI(APIView):
    def post(self,request):
        data = request.data
        try:
                                              
            converted_data = json.dumps(data,sort_keys=True, ensure_ascii=False)
            sha_256 = hashlib.sha256(converted_data.encode('utf-8')).hexdigest()
            sign = GLOBAL_PRIVATE_KEY.sign(bytes.fromhex(sha_256))
            data["Hash"] = str(sha_256)
            data["Firma"] = str(sign.hex())
            #TODO: Preparar json para guardarlo en ruta
            return Response({'success':'success'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'error': 'failed to save the file'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


#TODO: Creación de la API para la gestión de los Equipos de trabajo
class Grupos(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return[WorkerProfileOnly()]
        return [ControlProfileOnly()]
    



    def post(self, request):
        serializer = CrearGrupoSerializer(data=request.data)

        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                with transaction.atomic():
                    grupo = GrupoPersonal.objects.create(nombre_grupo=valid_data['nombre_grupo'])
                    for p_fk in valid_data['personal']:
                        persona = Personal.objects.get(id=p_fk)
                        SuscritosAGrupo.objects.create(grupo=grupo, personal=persona)
                return Response({'success':'success'}, status=status.HTTP_201_CREATED)
            except Personal.DoesNotExist:
                return Response({'error':'FATAL ERROR!: personal does not exists'}, status=status.HTTP_404_NOT_FOUND)
            except Exception:
                return Response({'error':'FATAL ERROR!: Failed to create the group'}, status=status.HTTP_406_NOT_ACCEPTABLE)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        serializer = RemoverMiembroGrupo(data=request.data)


        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                persona = get_object_or_404(Personal, id=valid_data['personal_id'])
                grupo_to_update = get_object_or_404(GrupoPersonal,id=valid_data['group_id'])
                with transaction.atomic():
                    SuscritosAGrupo.objects.filter(
                        grupo=grupo_to_update,
                        personal=persona,
                        fecha_salida=None
                    ).update(
                        fecha_salida=timezone.now()
                    )
                return Response({'success':'success'}, status=status.HTTP_200_OK)
            except Exception:
                return Response({'error':'FATAL ERROR!: failed to update the group'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def get(self, request):
        data = request.data
        query = SuscritosAGrupo.objects.filter(grupo_id=data.get('grupo_id'), fecha_salida=None).values(
            'personal__id', 'personal__first_name','personal__last_name','personal__rut','personal__rol__nombre_rol'
        )

        return Response(list(query), status=status.HTTP_200_OK)
    
class AddMemberToGroup(APIView):
    permission_classes = [ControlProfileOnly]
    def post(self, request):
        serializer = AgregarMiembroGrupo(data=request.data)

        if serializer.validated_data():
            valid_data = serializer.validated_data
            try:
                persona = get_object_or_404(Personal, id=valid_data['personal_id'])
                grupo_to_update = get_object_or_404(GrupoPersonal, id=valid_data['grupo_id'])
                with transaction.atomic():
                    SuscritosAGrupo.objects.create(grupo=grupo_to_update, 
                                                personal=persona, 
                                                fecha_salida=None)
                return Response({'success':'success'}, status=status.HTTP_201_CREATED)
            except Exception:
                return Response({'error':'FATAL ERROR! FAILED TO ADD MEMBER'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#TODO:Creacion de la API para el registro de los pacientes
class RegistrosPacientesAPI(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return[WorkerProfileOnly()]
        return [ControlProfileOnly()]

    def post(self, request):
        serializer = PacienteSerializer(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                Paciente.objects.create(rut=valid_data['rut'],
                nombre_completo=valid_data['full_name'], fecha_nacimiento=valid_data['date_birth'],
                direccion=valid_data['direccion'], condicion_paciente=valid_data['condicion_paciente'],
                telefono=valid_data['telefono'], comuna=valid_data['comuna'])
                return Response({'success':'success'}, status=status.HTTP_200_OK)
            except Exception:
                return Response({'error':'FATAL ERROR! FAILED TO ADD PATIENT'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    def get(self, request):
        data = request.data
        if 'id' in data:
            try:
                paciente = get_object_or_404(Paciente,id=data.get('id'))
                return Response(model_to_dict(paciente)
                                , status=status.HTTP_200_OK)
            except Exception:
                return Response({'error':'failed to get data'}, status=status.HTTP_404_NOT_FOUND)
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
        serializer = DespachoSerializer(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                with transaction.atomic():
                    Despacho.objects.create( direccion_origen=valid_data['d_o'],
                    direccion_destino=valid_data['d_d'],descripcion_llamado=valid_data['d_llamado'],
                    creado_por=request.user,estado='recibido')
                return Response({'success':'success'}, status=status.HTTP_201_CREATED)
            except Exception:
                return Response({'error':'FATAL ERROR NOT CREATED'}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class AsignarDespacho(APIView):
    permission_classes = [ControlProfileOnly]
    def patch(self, request):
        serializer = AsignarDespachoSerializer(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                amb = get_object_or_404(Ambulancia, id=valid_data['amb_id'])
                with transaction.atomic():
                    Despacho.objects.filter(id=valid_data['d_id']).update(
                        fecha_asignacion=timezone.now(),asignado_por=request.user,
                        ambulancia=amb, estado='asignado')
                    despacho=get_object_or_404(Despacho, id=valid_data['d_id'])
                    grupo_asign=get_object_or_404(GrupoPersonal, id=valid_data['grupo_id'])
                    DespachoPersonal.objects.create(despacho=despacho, grupo=grupo_asign)
                    return Response({'success':'success'},status=status.HTTP_200_OK)
            except Exception:
                return Response({'error':'failed to assign'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#TODO: Creacion de la API de logs para Auditorías -> para debatir
#TODO: Creación de la API de exportación de las atenciones en formatio FHIR HL7
#TODO: Creación de la API de tickets para recuperación de credenciales



# TESTING API DESPACHOS ASIGNADOS
class DespachoUsuarioAPI(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return[ControlProfileOnly()]
    def get(self, request):
        try:
            # buscar el grupo activo del usuario
            suscripcion = SuscritosAGrupo.objects.filter(
                personal=request.user,
                fecha_salida=None
            ).first()

            if not suscripcion:
                return Response([], status=status.HTTP_200_OK)

            # buscar despachos asignados a ese grupo
            despachos = DespachoPersonal.objects.filter(
                grupo=suscripcion.grupo
            ).select_related(
                'despacho',
                'despacho__ambulancia',
                'despacho__creado_por',
            ).exclude(
                despacho__estado__in=['finalizado', 'cancelado']
            )
            personal = SuscritosAGrupo.objects.filter(
                    grupo=suscripcion.grupo,
                    fecha_salida=None
                ).values(
                    'personal__id',
                    'personal__first_name',
                    'personal__last_name',
                    'personal__rut',
                    'personal__rol__nombre_rol',
            )
            resultado = []
            for dp in despachos:
                d = dp.despacho
                # obtener personal del grupo
                resultado.append({
                    'id': str(d.id),
                    'estado': d.estado,
                    'direccionOrigen': d.direccion_origen,
                    'direccionDestino': d.direccion_destino,
                    'descripcionLlamado': d.descripcion_llamado,
                    'fechaLlamado': d.fecha_llamado,
                    'ambulancia': {
                        'id': str(d.ambulancia.id),
                        'patente': d.ambulancia.patente,
                        'modelo': d.ambulancia.modelo,
                        'estado': d.ambulancia.estado_disponibilidad,
                    } if d.ambulancia else None,
                    'personalIds': [str(p['personal__id']) for p in personal],
                    'personal': list(personal),
                })

            return Response(resultado, status=status.HTTP_200_OK)
        except Exception:
            return Response({'error': 'failed to get the data'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#1-1 m-1
class AtencionAPI(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'},
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            atenciones = Atencion.objects.filter(
                registrado_por=request.user
            ).order_by('-fecha_registro').values(
                'id', 'fecha_registro', 'estado_sello'
            )
            return Response(list(atenciones), status=status.HTTP_200_OK)
        except Exception:
            return Response({'error': 'inner error'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'},
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            data = request.data
            despacho_id = data.get('despachoId')
            despacho = get_object_or_404(
                Despacho, id=despacho_id) if despacho_id else None
            atencion = Atencion.objects.create(
                registrado_por=request.user,
                despacho=despacho,
                datos_atencion=data,
            )
            return Response({'id': atencion.id},
                            status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': 'inner error'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AtencionDetalleAPI(APIView):
    def get(self, request, id):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado'},
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            atencion = get_object_or_404(
                Atencion,
                id=id,
                registrado_por=request.user
            )
            return Response({
                'id': atencion.id,
                'fecha_registro': atencion.fecha_registro,
                'datos_atencion': atencion.datos_atencion,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'inner error'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)