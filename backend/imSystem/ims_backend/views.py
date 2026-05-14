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
from django.conf import settings
from django.db.models import F
#---PYTHON INCLUDES IMPORTS---
import hashlib
import json
import decimal
import datetime
import base64
#---SERIALIZERS---
from .serializers import PersonalSerializer
from .serializers import CrearGrupoSerializer
from .serializers import RemoverMiembroGrupo
from .serializers import AgregarMiembroGrupo
from .serializers import PacienteSerializer
from .serializers import DespachoSerializer
from .serializers import AsignarDespachoSerializer
from .serializers import ParamSerializer
from .serializers import ParamPacienteSerializer
from .serializers import PayloadSerializer
from .serializers import ParamAtencionSerializer
#---PERSONAL MODULES IMPORTS---
from load_key import GLOBAL_PRIVATE_KEY
from . import utils
from utils import get_s3_download_url
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
from .models import SignosVitales
from .models import PreInforme
from .models import Cronologia
from .models import InsumoMedico
from .models import Documento
from .models import DetalleInsumoAtencion

#-----BOTO3----
import boto3
from botocore.exceptions import ClientError
s3_client = boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME)

#---CLASS PERMISSION BASED---
# Permiso custom: restringe acceso a usuarios con rol control
# Usar en vistas donde solo personal de control debe operar (como por ejemplo asignar trabajores, despachos etc)
class ControlProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol and request.user.rol.nombre_rol == 'control')
class MedicProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol and request.user.rol.nombre_rol == 'medic')    
class NurseProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol and request.user.rol.nombre_rol == 'nurse')
    
class DriverProfileOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol and request.user.rol.nombre_rol == 'driver')

class WorkerProfileOnly(BasePermission):
    def has_permission(self, request,view):
        return bool(request.user.is_authenticated and request.user.rol and request.user.rol.nombre_rol in ['medic', 'nurse', 'driver'])


#--CSRF TOKEN METHOD CLASS---
class EnsureCsrfMixin:
    @method_decorator(ensure_csrf_cookie)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
#----ENCODER---
class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)
#----CLASS BASED VIEWS----
class Login(EnsureCsrfMixin, APIView):
    #TODO: Implementacion de MFA con Google Authenticator (TOTP)
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({}, status=status.HTTP_200_OK)
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
            
            if user.rol is None:
                return Response({'error':'User with no role assigned'}, status=status.HTTP_403_FORBIDDEN)
            else:
                login(request,user)
                return Response({'success':'success', 'role': user.rol.nombre_rol}, status=status.HTTP_200_OK)
        except ValueError:
            return Response({'error':'wrong values check again'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception:
            return Response({'error':'inner error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




#TODO: Creacion de la api para cargar y actualizar datos del inventario
class Inventory(APIView):
    permission_classes  = [ControlProfileOnly]



#API de las ambulancias
class AmbulanciaAPI(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [ControlProfileOnly()]
    

    def get(self, request):
        data_ambulancias = Ambulancia.objects.all().values('id', 'patente','modelo','estado_disponibilidad')
        return Response(list(data_ambulancias), status=status.HTTP_200_OK)


#API para obtener datos del personal
class DataPersonal(APIView):
    def get_permissions(self):
        # Paréntesis agregados para instanciar las clases correctamente
        if self.request.method == 'GET':
            return [WorkerProfileOnly()]
        return [ControlProfileOnly()]

    def get(self, request):
        personal_activo = Personal.objects.filter(is_active=True).select_related('rol')
        

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
class RegistroAtencionAPI(APIView):
    permission_classes = [WorkerProfileOnly]
    def post(self,request):
        serializer = PayloadSerializer(data= request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            svd = valid_data['signos_vitales']
            preinforme_data = valid_data['preinforme']
            cronologia_data = valid_data['cronologia']
            insumos_data = valid_data['insumos_utilizados']
            despacho_data = valid_data['despacho']
            despacho = get_object_or_404(Despacho, id=despacho_data['despacho_id'])
            paciente = get_object_or_404(Paciente, id=despacho_data['paciente_id'])
            ambulancia = get_object_or_404(Ambulancia, id=despacho_data['ambulancia_id'])
            if despacho.estado != "asignado":
                return Response({'error':'cannot edit'}, status=status.HTTP_400_BAD_REQUEST)
            if Atencion.objects.filter(despacho=despacho).exists():
                return Response({'error':'cannot edit same data twice'}, status=status.HTTP_409_CONFLICT)
            try:
                with transaction.atomic():
                    
                    atencion = Atencion.objects.create(paciente=paciente, ambulancia=ambulancia, despacho=despacho,
                                            direccion_despacho=despacho_data['direccion_despacho'],
                                            hora_salida=despacho_data['hora_salida'],
                                            hora_llegada=despacho_data['hora_llegada'])
                    SignosVitales.objects.bulk_create([SignosVitales(atencion=atencion, **sv) for sv in svd])
                    pre=PreInforme.objects.create(atencion=atencion, pre_informe=preinforme_data['pre_informe'],
                                                           motivo_llamado=preinforme_data['motivo_llamado'],
                                                           estado_paciente=preinforme_data['estado_paciente'])
                    crono =Cronologia.objects.create(atencion=atencion, hora_llamada=cronologia_data['hora_llamada'],
                                                                despacho_movil = cronologia_data['despacho_movil'],
                                                                llegada_qth1=cronologia_data['llegada_qth1'],
                                                                salida_qth1=cronologia_data['salida_qth1'],
                                                                llegada_qth2=cronologia_data['llegada_qth2'],
                                                                salida_qth2=cronologia_data['salida_qth2'],
                                                                categoria=cronologia_data['categoria'])
                    ids_insumos = [item['insumo_id'] for item in insumos_data]
                    insumos_locked = {i.id: i for i in InsumoMedico.objects.select_for_update().filter(id__in=ids_insumos)}
                    
                    for insumo_data in insumos_data:
                        insumo = insumos_locked[insumo_data['insumo_id']]
                        if insumo.stock_total < insumo_data['dosis']:
                            raise ValueError(f"Stock insuficiente para {insumo.nombre_insumo}")
                    for insumo_data in insumos_data:
                        InsumoMedico.objects.filter(id=insumo_data['insumo_id']).update(
                            stock_total=F('stock_total') - insumo_data['dosis']
                        )
                        DetalleInsumoAtencion.objects.create(
                            atencion=atencion,
                            insumo_id=insumo_data['insumo_id'],
                            dosis=insumo_data['dosis'],
                            observaciones=insumo_data['observaciones']
                        )
                    document = {
                        "despacho": model_to_dict(atencion),
                        "signos_vitales":list(SignosVitales.objects.filter(atencion=atencion)
                                                                    .values(
                                                                        'id',
                                                                        'atencion_id',
                                                                        'timestamp',
                                                                        'presion_sistolica',
                                                                        'presion_diastolica',
                                                                        'frecuencia_cardiaca',
                                                                        'saturacion_oxigeno',
                                                                        'temperatura',
                                                                        'fr',
                                                                        'fio2',
                                                                        'hgt',
                                                                        'gcs',
                                                                        'eva',
                                                                        'hora',
                                                                        'observaciones'
                                                                    )),
                        "preinforme":model_to_dict(pre),
                        "cronologia":model_to_dict(crono),
                        "insumos_utilizados":list(DetalleInsumoAtencion.objects.filter(atencion=atencion)
                                                   .values('insumo__nombre_insumo','dosis','observaciones')),
                    }
                    prepared_data = json.dumps(document, sort_keys=True, ensure_ascii=False, cls=CustomEncoder)
                    sha_256 = hashlib.sha256(prepared_data.encode('utf-8')).digest()
                    sha_256_hex = sha_256.hex()
                    sign = GLOBAL_PRIVATE_KEY.sign(sha_256)
                    firma_b64 = base64.b64encode(sign).decode('utf-8')
                    document["Hash"]= sha_256_hex
                    document["Firma"]= firma_b64

                    atencion.sello_electronico= f"{sha_256_hex}:{firma_b64}"
                    atencion.estado_sello="Firmado"
                    atencion.save(update_fields=["sello_electronico","estado_sello"])
                    s3_key_json = f"documentos/{sha_256_hex}.json"
                    s3_key_sig  = f"documentos/{sha_256_hex}.sig"
                    Documento.objects.create(archivo_s3_key=s3_key_json,
                                             firma_s3_key=s3_key_sig,
                                             archivo_hash=sha_256_hex,
                                             atencion=atencion)
            except ValueError as ve:
                return Response({"error":str(ve)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"error":str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            try:
                bucket_name = settings.AWS_STORAGE_BUCKET_NAME
                file_json = json.dumps(document, ensure_ascii=False, cls=CustomEncoder)
                s3_client.put_object(
                            Bucket=bucket_name,
                            Key=f"documentos/{document["Hash"]}.json",
                            Body=file_json.encode('utf-8'),
                            ContentType='application/json'
                        )
                s3_client.put_object(
                            Bucket=bucket_name,
                            Key=f'documentos/{document["Hash"]}.sig',
                            Body=base64.b64encode(sign).decode('utf-8'),
                            ContentType='application/octet-stream'
                        )
                return Response({"success":"Succeeded", "hash": sha_256_hex}, status=status.HTTP_201_CREATED)
            except Exception:
                return Response({"error":"Failed to upload to S3"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 


#Creación de la API para la gestión de los Equipos de trabajo
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
                    personas = Personal.objects.filter(id__in=valid_data['personal'])
                    SuscritosAGrupo.objects.bulk_create([
                        SuscritosAGrupo(grupo=grupo, personal=persona)
                        for persona in personas
                    ])
                return Response({'success':'success'}, status=status.HTTP_201_CREATED)
            except Personal.DoesNotExist:
                return Response({'error':'FATAL ERROR!: personal does not exists'}, status=status.HTTP_404_NOT_FOUND)
            except Exception:
                return Response({'error':'FATAL ERROR!: Failed to create the group'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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
        if request.query_params:
            serializer = ParamSerializer(data=request.query_params)

            if serializer.is_valid():
                valid_data = serializer.validated_data
                query = SuscritosAGrupo.objects.filter(grupo_id=valid_data['group_id'], fecha_salida=None).values(
                    'personal__id', 'personal__first_name','personal__last_name','personal__rut','personal__rol__nombre_rol'
                )
                return Response(list(query), status=status.HTTP_200_OK)
            else:
                return Response({'error':'not correct format or id'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            query = SuscritosAGrupo.objects.filter(fecha_salida=None).values(
                    'personal__id', 'personal__first_name','personal__last_name','personal__rut','personal__rol__nombre_rol'
                )
            return Response(list(query), status=status.HTTP_200_OK)
class AddMemberToGroup(APIView):
    permission_classes = [ControlProfileOnly]
    def post(self, request):
        serializer = AgregarMiembroGrupo(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                persona = get_object_or_404(Personal, id=valid_data['personal_id'])
                grupo_to_update = get_object_or_404(GrupoPersonal, id=valid_data['grupo_id'])
                if SuscritosAGrupo.objects.filter(grupo=grupo_to_update,
                                                  personal=persona,fecha_salida=None).exists():
                    return  Response({'error':'person already in a group'}, status=status.HTTP_409_CONFLICT)
                with transaction.atomic():
                    SuscritosAGrupo.objects.create(grupo=grupo_to_update, 
                                                personal=persona, 
                                                fecha_salida=None)
                return Response({'success':'success'}, status=status.HTTP_201_CREATED)
            except Exception:
                return Response({'error':'FATAL ERROR! FAILED TO ADD MEMBER'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#API para el registro de los pacientes
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
        if request.query_params:
            serialize = ParamPacienteSerializer(data=request.query_params)
            if serialize.is_valid():
                valid_data = serialize.validated_data
                try:
                    paciente = get_object_or_404(Paciente,rut=valid_data['rut'])
                    return Response(model_to_dict(paciente)
                                    , status=status.HTTP_200_OK)
                except Exception:
                    return Response({'error':'failed to get data'}, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({'error':'invalid format or check the correct rut?'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            pacientes = Paciente.objects.all().values(
                    'rut', 'nombre_completo', 'fecha_nacimiento',
                    'direccion', 'condicion_paciente', 'telefono', 'comuna'
                )
            return Response(list(pacientes), status=status.HTTP_200_OK)

#TODO: Creación de la API para los estados de los usuarios (en turno, disponible, fuera de servicio)
#TODO: Creación de la API para la gestión de los datos de los pacientes(para cargar al documento)
#Creacion de la API para despachar las atenciones
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
                return Response({'error':'FATAL ERROR NOT CREATED'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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









#IGNORAR DE AQUI PARA ABAJO
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
class AtencionAPI(APIView):
    permission_classes=[IsAuthenticated]
    
    def get(self, request):
        if request.query_params:
            serializer = ParamAtencionSerializer(data=request.query_params)
            if serializer.is_valid():
                valid_data=serializer.validated_data
                try:
                    atencion =  get_object_or_404(Atencion, id=valid_data['id'])
                    document = atencion.documentos.first()
                    if not document:
                        return Response({'error': 'No document found for this atencion'}, status=status.HTTP_404_NOT_FOUND)
                    response = get_s3_download_url(document.archivo_s3_key, 3600)
                    return Response({"success":f"{response}"}, status=status.HTTP_200_OK)
                except ClientError:
                    return Response({"error":"failed to generate the url"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(list(Atencion.objects.select_related('paciente').all().values('id', 'hora_salida', 'hora_llegada', 'estado_sello', 'paciente__nombre_completo')), status=status.HTTP_200_OK)