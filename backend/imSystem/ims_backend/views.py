# ─── DJANGO REST FRAMEWORK ───────────────────────────────────────────────────
from rest_framework.views       import APIView
from rest_framework             import status
from rest_framework.response    import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny

# ─── DJANGO ──────────────────────────────────────────────────────────────────
from django.contrib.auth            import authenticate, login
from django.shortcuts               import get_object_or_404
from django.utils                   import timezone
from django.db                      import transaction
from django.forms.models            import model_to_dict
from django.utils.decorators        import method_decorator
from django.views.decorators.csrf   import ensure_csrf_cookie


# ─── SERIALIZERS ─────────────────────────────────────────────────────────────
from .serializers import PersonalSerializer
from .serializers import CrearGrupoSerializer
from .serializers import RemoverMiembroGrupo
from .serializers import AgregarMiembroGrupo
from .serializers import PacienteSerializer
from .serializers import CreateDespachoSerializer
from .serializers import AsignarDespachoSerializer
from .serializers import ParamSerializer
from .serializers import ParamPacienteSerializer
from .serializers import PayloadSerializer
from .serializers import ParamAtencionSerializer
from .serializers import ObtenerDespachoSerializer
from .serializers import AuthenticationSerializer
# ─── MODELS ──────────────────────────────────────────────────────────────────
from .models import Personal
from .models import Paciente
from .models import SuscritosAGrupo
from .models import GrupoPersonal
from .models import RolPersonal
from .models import Despacho
from .models import Ambulancia
from .models import DespachoPersonal
from .models import Atencion
# ─── LOCAL / AWS ─────────────────────────────────────────────────────────────
from ims_backend.toolbox.Atenciones.add_atencion import add_atencion
from ims_backend.toolbox.Despachos.all_despachos import all_despachos
from ims_backend.toolbox.Despachos.solicitud_usuario import solicitud_usuario
from ims_backend.toolbox.Inventario import (gets)
from ims_backend.toolbox.Ambulancias import (gets)
from .utils              import(get_s3_download_url, generate_totp, generate_password)
from botocore.exceptions import ClientError
from .totp_auth.authentication import authentication
# =============================================================================
# PERMISOS PERSONALIZADOS
# =============================================================================

# Permiso custom: restringe acceso a usuarios con rol control
# Usar en vistas donde solo personal de control debe operar (como por ejemplo asignar trabajores, despachos etc)
from ims_backend.auth.permissions import (ControlProfileOnly,
                              NurseProfileOnly, DriverProfileOnly,
                              MedicProfileOnly,MFAVerified)

# =============================================================================
# UTILIDADES
# =============================================================================

class EnsureCsrfMixin:
    @method_decorator(ensure_csrf_cookie)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

# =============================================================================
# VISTAS
# =============================================================================

# API para INICIAR sesion en la aplicacion
class Login(EnsureCsrfMixin, APIView):
    #TODO: Implementacion de MFA con Google Authenticator (TOTP)
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AuthenticationSerializer(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                user = authenticate (
                        request,
                        username = valid_data['username'],
                        password = valid_data['password']
                )
                if user is None:
                    return Response(
                        {'error':'Fallo al cargar al usuario, estás seguro de haber ingresado las credenciales correctas?'}
                        ,status=status.HTTP_401_UNAUTHORIZED)
                if authentication(user.totp_secret, valid_data['totp_code']):
                        
                    if user.rol is None:
                            return Response({'error':'User with no role assigned'}, status=status.HTTP_403_FORBIDDEN)
                    else:
                            login(request,user)
                            request.session.save()
                            request.session['mfa_verified'] = True
                            return Response({'success':'success', 'sessionid':request.session.session_key,'role': user.rol.nombre_rol}, status=status.HTTP_200_OK)
                else: 
                    return Response({"error":'TOTP failed'}, status=status.HTTP_401_UNAUTHORIZED)
            except ValueError:
                return Response({'error':'wrong values check again'}, status=status.HTTP_401_UNAUTHORIZED)
            except Exception as e:
                    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── TODO ─────────────────────────────────────────────────────────────────────
#TODO: Creacion de la api para cargar y actualizar datos del inventario
class Inventory(APIView):
    permission_classes  = [ControlProfileOnly]


#API para obtener TODOS los insumos
class InsumosAPI(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [MFAVerified()]
        return [ControlProfileOnly()]
    def get(self, request):
        if request.query_params:
            r = gets.get_perid(request)
            return Response(r,status=status.HTTP_200_OK)
        else:
            return None
# API para OBTENER las ambulancias
class AmbulanciaAPI(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [ControlProfileOnly()]

    def get(self, request):
        if request.query_params:
            r = gets.get_perid(request)
            return Response(r, status=status.HTTP_200_OK)
        else:
            r = gets.get_all()
            return Response(r, status=status.HTTP_200_OK)

# API para OPERAR datos del personal
class DataPersonal(APIView):
    def get_permissions(self):
        # Paréntesis agregados para instanciar las clases correctamente
        if self.request.method == 'GET':
            return [MFAVerified()]
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

                key, totp = generate_totp()
                temp = generate_password()
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


# ─── TODO ─────────────────────────────────────────────────────────────────────
#TODO: Creacion de la validación del TOTP (MFA)
#TODO: Creación de la API de notificaciones -> SSE
#TODO: Creación de la API para carga de documentos y descarga de documentos (SOLO lectura, generar un QR desde HASH) -> prioridad


# API para REGISTRAR las atenciones post-despacho y subir los documentos firmados al S3
class RegistroAtencionAPI(APIView):
    permission_classes = [NurseProfileOnly | MedicProfileOnly]

    def post(self,request):
        result = add_atencion(request)
        return Response(result, status=status.HTTP_201_CREATED)

# API para creacion de GRUPOS de trabajo
class Grupos(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return[IsAuthenticated()]
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
                return Response({'success':'success', 'group_id': grupo.id}, status=status.HTTP_201_CREATED)
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
                grupos = {}
                suscripciones = SuscritosAGrupo.objects.filter(
                    grupo_id=valid_data['group_id'],fecha_salida=None
                ).select_related('grupo', 'personal', 'personal__rol')
                for suscripcion in suscripciones:
                    grupo_id = suscripcion.grupo.id
                    if grupo_id not in grupos:
                        grupos[grupo_id] = {
                            'grupo_id': grupo_id,
                            'grupo_nombre': suscripcion.grupo.nombre_grupo,
                            'miembros': []
                        }
                    grupos[grupo_id]['miembros'].append({
                        'nombre': suscripcion.personal.full_name,
                        'rut': suscripcion.personal.rut,
                        'rol': suscripcion.personal.rol.nombre_rol if suscripcion.personal.rol else None,
                        'dia_ingresado': suscripcion.fecha_entrada,
                        'dia_salida': suscripcion.fecha_salida
                    })
                    return Response(list(grupos.values()), status=status.HTTP_200_OK)
            else:
                return Response({'error':'not correct format or id'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            grupos = {}
            suscripciones = SuscritosAGrupo.objects.filter(
                fecha_salida=None
            ).select_related('grupo', 'personal', 'personal__rol')
            
            for suscripcion in suscripciones:
                grupo_id = suscripcion.grupo.id
                if grupo_id not in grupos:
                    grupos[grupo_id] = {
                        'grupo_id': grupo_id,
                        'grupo_nombre': suscripcion.grupo.nombre_grupo,
                        'miembros': []
                    }
                grupos[grupo_id]['miembros'].append({
                    'nombre': suscripcion.personal.full_name,
                    'rut': suscripcion.personal.rut,
                    'rol': suscripcion.personal.rol.nombre_rol if suscripcion.personal.rol else None,
                    'dia_ingresado': suscripcion.fecha_entrada,
                    'dia_salida': suscripcion.fecha_salida
                })
            return Response(list(grupos.values()), status=status.HTTP_200_OK)


# API para AÑADIR miembros a grupos YA EXISTENTES
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


# API para el registro de los pacientes
class RegistrosPacientesAPI(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return[IsAuthenticated()]
        return [ControlProfileOnly()]

    def post(self, request):
        serializer = PacienteSerializer(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                Paciente.objects.create(rut=valid_data['rut'],
                nombre_completo=valid_data['nombre_completo'],
                fecha_nacimiento=valid_data['fecha_nacimiento'],
                direccion=valid_data['direccion'],
                condicion_paciente=valid_data['condicion_paciente'],
                telefono=valid_data['telefono'], 
                comuna=valid_data['comuna'])
                return Response({'success':'success'}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error':f'{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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


# ─── TODO ─────────────────────────────────────────────────────────────────────
#TODO: Creación de la API para los estados de los usuarios (en turno, disponible, fuera de servicio)
#TODO: Creación de la API para la gestión de los datos de los pacientes(para cargar al documento)
# API para CREAR los despachos
class CreateDespacho(APIView):
    permission_classes = [ControlProfileOnly]
    def post(self, request):
        serializer = CreateDespachoSerializer(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                paciente = get_object_or_404(Paciente, rut=valid_data['paciente_rut'])
                with transaction.atomic():
                    despacho = Despacho.objects.create(
                        direccion_origen=valid_data['direccion_origen'],
                        direccion_destino=valid_data['direccion_destino'],
                        descripcion_llamado=valid_data['descripcion_llamado'],
                        paciente = paciente,
                        creado_por=request.user,
                        estado='recibido'
                    )
                return Response({'success':'success', 
                                 'despacho':
                                 {'id':despacho.id, 
                                  'paciente':
                                    {'rut':paciente.rut, 
                                     'nombre': paciente.nombre_completo
                                    }
                                  }}, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({'error':f'FATAL ERROR NOT CREATED:{e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# API para asignar los despachos a un grupo previamente creado y existente
class AsignarDespacho(APIView):
    permission_classes = [ControlProfileOnly]
    def patch(self, request):
        serializer = AsignarDespachoSerializer(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                amb = get_object_or_404(Ambulancia, id=valid_data['amb_id'])
                with transaction.atomic():
                    Despacho.objects.filter(id=valid_data['despacho_id']).update(
                        fecha_asignacion=timezone.now(),asignado_por=request.user,
                        ambulancia=amb, estado='asignado')
                    despacho=get_object_or_404(Despacho, id=valid_data['despacho_id'])
                    grupo_nombre=get_object_or_404(GrupoPersonal, id=valid_data['grupo_id'])
                    if DespachoPersonal.objects.filter(despacho=despacho, grupo=grupo_nombre).exists():
                        return Response({'error': 'Este grupo ya está asignado a este despacho'}, status=status.HTTP_409_CONFLICT)
                    DespachoPersonal.objects.create(despacho=despacho, grupo=grupo_nombre)
                    grupo_miembros = SuscritosAGrupo.objects.filter(grupo=grupo_nombre,fecha_salida = None )
                    personal = []
                    for members in grupo_miembros:
                        personal.append({'personal_id':members.personal.id,
                                         'personal_rut': members.personal.rut,
                                         'personal_name':members.personal.full_name})
                    
                    return Response({'success':'success', 'despacho_data':{
                        'id':valid_data['despacho_id'],
                        'grupo':{
                            'nombre':grupo_nombre.nombre_grupo,
                            'personal':personal
                        }
                    }},status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error':f'failed to assign: {e}'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# API para obtener TODOS Los despachos sin necesidad de incluir al usuario per se
class AllDespachos(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        r = all_despachos(request)
        return Response(r, status=status.HTTP_200_OK)


# ─── TODO ─────────────────────────────────────────────────────────────────────
#TODO: Creacion de la API de logs para Auditorías -> para debatir
#TODO: Creación de la API de exportación de las atenciones en formatio FHIR HL7
#TODO: Creación de la API de tickets para recuperación de credenciales


# API para retornar el despacho asignado al USUARIO LOGEADO AL MOMENTO DE HACER LA SOLICITUD, diferenciar de arriba que retorna todos los despachos
class DespachoASolicitudUsuario(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return[ControlProfileOnly()]

    def get(self, request):
        r = solicitud_usuario(request)
        return Response({r}, status=status.HTTP_200_OK)
       


# API para retornar las atenciones, recibe parámetros a través de URL
class RetornarAtencionAPI(APIView):
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
            atencion = Atencion.objects.select_related('despacho__paciente').all()
            response = []
            for a in atencion:
                response.append({
                    'atencion_id': a.id,
                    'hora_salida':a.hora_salida,
                    'hora_llegada':a.hora_llegada,
                    'estado_sello':a.estado_sello,
                    'firma_digital': a.sello_electronico,
                    'despacho':{
                        'despacho_id':a.despacho.id,
                        'paciente':{
                            'nombre':a.despacho.paciente.nombre_completo,
                            'rut':a.despacho.paciente.rut
                        } if a.despacho.paciente else None,
                    }if a.despacho else None
                })
            return Response(response, status=status.HTTP_200_OK)