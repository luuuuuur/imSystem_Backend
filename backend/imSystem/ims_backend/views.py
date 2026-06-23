# ─── DJANGO REST FRAMEWORK ───────────────────────────────────────────────────
from rest_framework.views       import APIView
from rest_framework.response    import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
# ─── DJANGO ──────────────────────────────────────────────────────────────────
from django.contrib.auth            import logout as django_logout
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
from .serializers import ParamPacienteSerializer
from .serializers import AuthenticationSerializer
from .serializers import ProgramarDespachoSerializer
from .serializers import DeviceToken
from .serializers import AddAmbulanciaSerializer
from .serializers import CancelarDespachoSerializer
# ─── MODELS ──────────────────────────────────────────────────────────────────
from .models import Personal
from .models import Paciente
from .models import SuscritosAGrupo
from .models import GrupoPersonal
from .models import RolPersonal
from .models import Despacho
from .models import Ambulancia
from .models import DespachoPersonal
from .models import LogAuditoria
from .models import Atencion
from .models import Documento
# ─── LOCAL / AWS ─────────────────────────────────────────────────────────────
from ims_backend.toolbox.Atenciones_package.add_atencion import add_atencion
from ims_backend.toolbox.Atenciones_package.return_noquery import atencion_noquery
from ims_backend.toolbox.Atenciones_package.return_with_query import atencion_with_query
from ims_backend.toolbox.Despachos_package.all_despachos import all_despachos
from ims_backend.toolbox.Despachos_package.solicitud_usuario import solicitud_usuario
from .toolbox.Inventario_package import add, gets as gets_inventario, update
from .toolbox.Ambulancia_package import gets as gets_ambulancia, move,cambiar_estado
from .utils              import(generate_totp, generate_password)
from ims_backend.toolbox.exceptions import (ConflictException, BadRequestException,
                                              InternalServerException, NotFoundException,
                                              UnAuthorizedException, ForbiddenException)
from ims_backend.task_package.task_log_grupos import crear_grupo_log, agregar_miembros_log,actualizar_estado_miembros_log
from ims_backend.task_package.task_log_paciente import agregar_paciente_log
from ims_backend.task_package.task_log_despacho import crear_despacho_log, asignar_despacho_log, cambiar_estado_log, cancelar_despacho_log
from ims_backend.task_package.task_log_personal import agregar_personal_log
from ims_backend.task_package.task_log_ambulancias import agregar_ambulancia_log
from ims_backend.toolbox.Fhir_package.export_r4 import export_hl7
from ims_backend.toolbox.Grupos_package.no_query_params import no_query_params
from ims_backend.toolbox.Grupos_package.get_with_query import with_query
from ims_backend.toolbox.Despachos_package.change_status import change_despacho_status
from ims_backend.task_package.task_notificaciones import notificacion
from ims_backend.toolbox.Personal_package.set_device_token import set_device

# =============================================================================
# PERMISOS PERSONALIZADOS
# =============================================================================

# Permiso custom: restringe acceso a usuarios con rol control
# Usar en vistas donde solo personal de control debe operar (como por ejemplo asignar trabajores, despachos etc)
from ims_backend.auth_package.permissions import (ControlProfileOnly,
                                                  NurseProfileOnly, MedicProfileOnly, MFAVerified,
                                                  MFAAndAnyProfile, MFAAndClinicalProfile, MFAAndMedicalStaff,
                                                  MFAAndFieldStaff)

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
from ims_backend.totp_auth.autenticar_user import autenticar as auth_user
from ims_backend.totp_auth.autenticar_user import iniciar_sesion

class Authenticate(APIView):
    permission_classes = [AllowAny]
    http_method_names = ['post']

    def post(self, request):
        serializer = AuthenticationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                auth_user(request, serializer.validated_data)
                return Response({}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

from ims_backend.serializers import LoginSerializer
class Login(EnsureCsrfMixin, APIView):
    permission_classes = [AllowAny]
    http_method_names = ['get', 'post']

    def get(self, request):
        return Response({}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            try:
                r = iniciar_sesion(request, serializer.validated_data)
                return Response(r, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#TOKEN DEVICE
#/api/token/post/
class Logout(APIView):
    http_method_names = ['post']
    permission_classes = [AllowAny]

    def post(self, request):
        django_logout(request)
        return Response({}, status=status.HTTP_200_OK)


class TokenPOST(APIView):
    http_method_names= ['post']
    permission_classes = [MFAVerified]
    def post(self, request):
        serializer = DeviceToken(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                set_device(request.user.id, valid_data["token"])
                return Response({'success': 'success'}, status=status.HTTP_201_CREATED)
            except Exception as e:
                raise InternalServerException(detail=str(e))
        else:
            raise BadRequestException
#ADMINISTRACION----------------------

# #API para obtener TODOS los insumos
class GetInsumosAPI(APIView):
    http_method_names = ['get']
    permission_classes = [ControlProfileOnly & MFAVerified]
    
    def get(self, request):
        if request.query_params:
            r = gets_inventario.get_perid(request.query_params)
            return Response(r,status=status.HTTP_200_OK)
        else:
            r = gets_inventario.get_all()
            return Response(r, status=status.HTTP_200_OK)
class AddInsumoAPI(APIView):
    permission_classes = [ControlProfileOnly & MFAVerified]
    http_method_names = ['post']
    def post(self, request):
        r = add.add(request.data, request.user)
        return Response({}, status=status.HTTP_201_CREATED)

class UpdateStockAPI(APIView):
    http_method_names = ['patch']
    permission_classes = [ControlProfileOnly & MFAVerified]
    def patch(self, request):
        r = update.update(request.data, request.user)
        return  Response({}, status=status.HTTP_200_OK)
class MoveInsumoAPI(APIView):
    http_method_names = ['patch']
    permission_classes = [ControlProfileOnly & MFAVerified]

    def patch(self, request):
        r = move.move_item(request.data, request.user)
        return Response({}, status=status.HTTP_200_OK)
# API para OBTENER las ambulancias
class AmbulanciaAPI(APIView):
    http_method_names = ['get']
    permission_classes = [MFAAndAnyProfile]

    def get(self, request):
        if request.query_params:
            r = gets_ambulancia.get_perid(request.query_params)
            return Response(r, status=status.HTTP_200_OK)
        else:
            r = gets_ambulancia.get_all()
            return Response(r, status=status.HTTP_200_OK)

class AddAmbulanciaAPI(APIView):
    http_method_names = ['post']
    permission_classes = [ControlProfileOnly & MFAVerified]

    def post(self, request):
        serializer = AddAmbulanciaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        valid_data = serializer.validated_data
        try:
            with transaction.atomic():
                ambulancia = Ambulancia.objects.create(
                    patente=valid_data['patente'],
                    modelo=valid_data['modelo'],
                    estado_disponibilidad=valid_data['estado_disponibilidad'],
                )
                log_data = {
                    'user_id': request.user.id,
                    'patente': ambulancia.patente,
                    'modelo': ambulancia.modelo,
                    'ambulancia_id': ambulancia.id,
                }
                transaction.on_commit(lambda: agregar_ambulancia_log.delay(data=log_data))
            return Response({'success': 'success', 'ambulancia_id': ambulancia.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)

# API para obtener los datos del personal
class GetPersonal(APIView):
    http_method_names = ['get']
    permission_classes = [MFAAndAnyProfile]
    def get(self, request):
        personal_activo = Personal.objects.filter(is_active=True).select_related('rol')
        serializer = PersonalSerializer(personal_activo, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

#APi para OPERAR datos del personal
class AddPersonal(APIView):
    http_method_names = ['post']
    permission_classes = [MFAVerified & ControlProfileOnly]
    #Agregar un trabajador
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
                
                with transaction.atomic():
                    usuario = Personal.objects.create_user(
                        username=rut,
                        first_name=first_name,
                        last_name=last_name,
                        password=temp,
                        totp_secret=key,
                        rut=rut,
                        rol=rol
                    )
                    log_data = {
                        "rut": request.user.rut,
                        "user_id":request.user.id,
                        "rut_trabajador":usuario.rut
                    }
                    transaction.on_commit(lambda: agregar_personal_log.delay(data=log_data))
                return Response({
                        'success': 'success', 
                        'totp_uri': uri, 
                        'password': temp,
                        'usuario_id': usuario.id
                    }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({'error': f'failed to generate the uri and user data + {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#Adaptar a solo desactivar pero no borrar registros del personal 
class DeletePersonal(APIView):
    http_method_names = ['delete']
    permission_classes = [MFAVerified & ControlProfileOnly]

    def delete(self, request):
        personal_id = request.query_params.get('personal_id')
        if not personal_id:
            return Response({'error': 'personal_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        personal = get_object_or_404(Personal, id=personal_id)

        if personal.pk == request.user.pk:
            return Response({'error': 'No puedes eliminarte a ti mismo'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                Despacho.objects.filter(creado_por=personal).update(creado_por=None)
                Despacho.objects.filter(asignado_por=personal).update(asignado_por=None)

                atenciones = Atencion.objects.filter(rut_registrador=personal)
                LogAuditoria.objects.filter(atencion__in=atenciones).update(atencion=None)
                Documento.objects.filter(atencion__in=atenciones).delete()
                atenciones_eliminadas = atenciones.delete()[0]

                suscripciones_eliminadas = SuscritosAGrupo.objects.filter(personal=personal).delete()[0]
                LogAuditoria.objects.filter(usuario=personal).delete()
                rut = personal.rut
                nombre = personal.get_full_name()
                personal.delete()

            return Response({
                'success': f'Personal {nombre} ({rut}) eliminado',
                'suscripciones_eliminadas': suscripciones_eliminadas,
                'atenciones_eliminadas': atenciones_eliminadas,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'No se puede eliminar: tiene registros asociados protegidos. Detalle: {str(e)}'},
                status=status.HTTP_409_CONFLICT,
            )



# API para REGISTRAR las atenciones post-despacho y subir los documentos firmados al S3
class RegistroAtencionAPI(APIView):
    http_method_names = ['post']
    permission_classes = [MFAAndMedicalStaff]
    def post(self,request):
        result = add_atencion(request.data, request.user)
        return Response(result, status=status.HTTP_201_CREATED)


class GruposObtener(APIView):
    http_method_names = ['get']
    permission_classes = [ControlProfileOnly & MFAVerified]
    def get(self, request):
        if request.query_params:
            r = with_query(request.query_params)
            return Response(r, status=status.HTTP_200_OK)
        
        r = no_query_params()
        return Response(r, status=status.HTTP_200_OK)

class GrupoCrear(APIView):
    http_method_names = ['post']
    permission_classes = [ControlProfileOnly & MFAVerified]
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
                    log_data = dict(valid_data)
                    log_data["user_id"] = request.user.id
                    log_data["rut"] = request.user.rut
                    transaction.on_commit(lambda:crear_grupo_log.delay(data = log_data))
                return Response({'success':'success', 'group_id': grupo.id}, status=status.HTTP_201_CREATED)
            except Personal.DoesNotExist:
                return Response({'error':'FATAL ERROR!: personal does not exists'}, status=status.HTTP_404_NOT_FOUND)
            except Exception:
                return Response({'error':'FATAL ERROR!: Failed to create the group'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GrupoRemoverMiembro(APIView):
    http_method_names = ['patch']
    permission_classes = [ControlProfileOnly & MFAVerified]
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
                    log_data = {
                        "personal_rut": persona.rut,
                        "group_id":grupo_to_update.id,
                        "group_name":grupo_to_update.nombre_grupo,
                        "rut":request.user.rut,
                        "user_id":request.user.id
                    }
                    transaction.on_commit(lambda:actualizar_estado_miembros_log.delay(data=log_data))
                return Response({'success':'success'}, status=status.HTTP_200_OK)
            except Exception:
                return Response({'error':'FATAL ERROR!: failed to update the group'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# API para AÑADIR miembros a grupos YA EXISTENTES
class AddMemberToGroup(APIView):
    http_method_names = ['post']
    permission_classes = [ControlProfileOnly & MFAVerified]
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
                    log_data = {
                        "user_id":request.user.id,
                        "rut":request.user.rut,
                        "group_id": grupo_to_update.id,
                        "group_nombre":grupo_to_update.nombre_grupo,
                        "personal_rut":persona.rut
                    }
                    transaction.on_commit(lambda: agregar_miembros_log.delay(data = log_data))
                return Response({'success':'success'}, status=status.HTTP_201_CREATED)
            except Exception:
                return Response({'error':'FATAL ERROR! FAILED TO ADD MEMBER'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# API para el registro de los pacientes
class RegistrosPacientesAPI(APIView):
    http_method_names = ['post']
    permission_classes = [MFAVerified & ControlProfileOnly]
    def post(self, request):
        serializer = PacienteSerializer(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                with transaction.atomic():
                    Paciente.objects.create(rut=valid_data['rut'],
                    nombre_completo=valid_data['nombre_completo'],
                    fecha_nacimiento=valid_data['fecha_nacimiento'],
                    direccion=valid_data['direccion'],
                    condicion_paciente=valid_data['condicion_paciente'],
                    telefono=valid_data['telefono'], 
                    comuna=valid_data['comuna'])
                    log_data = {
                        "paciente_rut": valid_data['rut'],
                        "id":request.user.id,
                        "rut":request.user.rut
                    }
                    transaction.on_commit(lambda: agregar_paciente_log.delay(data=log_data))
                return Response({'success':'success'}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error':f'{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GetPacientes(APIView):
    http_method_names = ["get"]
    permission_classes = [MFAVerified & ControlProfileOnly]
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


# API para CREAR los despachos
class CreateDespacho(APIView):
    http_method_names = ['post']
    permission_classes = [ControlProfileOnly & MFAVerified]
    def post(self, request):
        serializer = CreateDespachoSerializer(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                paciente = get_object_or_404(Paciente, rut=valid_data['paciente_rut'])
                log_data = {
                    "paciente_rut": paciente.rut,
                    "user_id":request.user.id,
                    "rut":request.user.rut
                }
                with transaction.atomic():
                    despacho = Despacho.objects.create(
                        direccion_origen=valid_data['direccion_origen'],
                        direccion_destino=valid_data['direccion_destino'],
                        descripcion_llamado=valid_data['descripcion_llamado'],
                        paciente = paciente,
                        creado_por= request.user,
                        estado=Despacho.RECIBIDO
                    )
                    log_data["despacho_id"]=despacho.id
                    transaction.on_commit(lambda: crear_despacho_log.delay(data=log_data))
                    transaction.on_commit(lambda: change_despacho_status(type=Despacho.RECIBIDO, despacho=despacho))
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
    http_method_names = ['patch']
    permission_classes = [ControlProfileOnly & MFAVerified]
    def patch(self, request):
        serializer = AsignarDespachoSerializer(data=request.data)
        if serializer.is_valid():
            valid_data = serializer.validated_data
            try:
                amb = get_object_or_404(Ambulancia, id=valid_data['amb_id'])
                _despacho=get_object_or_404(Despacho, id=valid_data['despacho_id'])
                grupo_nombre=get_object_or_404(GrupoPersonal, id=valid_data['grupo_id'])
                log_data = {
                    "patente":amb.patente,
                    "rut":request.user.rut,
                    "user_id":request.user.id,
                    "grupo_id":grupo_nombre.id,
                    "nombre_grupo": grupo_nombre.nombre_grupo,
                    "id":_despacho.id
                }
                if DespachoPersonal.objects.filter(despacho=_despacho, grupo=grupo_nombre).exists():
                    return Response({'error': 'Este grupo ya está asignado a este despacho'}, status=status.HTTP_409_CONFLICT)
                tipo_estado = Despacho.EMERGENCIA if valid_data["is_emergency"] else Despacho.ASIGNADO
                with transaction.atomic():
                    change_despacho_status(type=tipo_estado, despacho=_despacho, fecha_prog=None)
                    _despacho.ambulancia=amb
                    _despacho.asignado_por = request.user
                    _despacho.save(update_fields=["ambulancia","asignado_por"])
                    DespachoPersonal.objects.create(despacho=_despacho, grupo=grupo_nombre)
                    grupo_miembros = SuscritosAGrupo.objects.filter(grupo=grupo_nombre,fecha_salida = None )
                    personal = []
                    for members in grupo_miembros:
                        personal.append({'personal_id':members.personal.id,
                                         'personal_rut': members.personal.rut,
                                         'personal_name':members.personal.full_name})
                    transaction.on_commit(lambda: asignar_despacho_log.delay(data=log_data))
                if valid_data["is_emergency"]:
                    notificacion.delay(type=Despacho.EMERGENCIA, dir=_despacho.direccion_destino, grupo_id=grupo_nombre.id)
                else:
                    notificacion.delay(type=Despacho.ASIGNADO, grupo_id=grupo_nombre.id, despacho_id=_despacho.id)
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

#/api/despachos/programar/
class ProgramarDespacho(APIView):
    http_method_names = ['patch']
    permission_classes = [MFAVerified & ControlProfileOnly]
    #query_params -> Serializer -> Update despacho status function
    def patch(self, request):
        log_data = {
            "rut": request.user.rut,
            "user_id": request.user.id
        }
        serializer = ProgramarDespachoSerializer(data= request.data)
        if serializer.is_valid():
            _valid_data = serializer.validated_data
            try:
                with transaction.atomic():
                    _despacho = get_object_or_404(Despacho, id=_valid_data["despacho_id"])
                    _grupo    = get_object_or_404(GrupoPersonal, id=_valid_data["grupo_id"])
                    change_despacho_status(type=Despacho.PROGRAMADO, despacho=_despacho,fecha_prog=_valid_data["fecha_programada"])
                    DespachoPersonal.objects.get_or_create(despacho=_despacho, grupo=_grupo)
                    log_data["despacho_id"] = _valid_data["despacho_id"]
                    log_data["estado"] = Despacho.PROGRAMADO
                    transaction.on_commit(lambda: cambiar_estado_log.delay(data=log_data))
                    transaction.on_commit(lambda: notificacion.delay(type=Despacho.PROGRAMADO, grupo_id=str(_valid_data["grupo_id"]), fecha=str(_despacho.fecha_programada)))
                return Response({}, status=status.HTTP_200_OK)
            except Exception as e: return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else: return Response({}, status=status.HTTP_400_BAD_REQUEST)
        

class CancelarDespacho(APIView):
    http_method_names = ['patch']
    permission_classes = [ControlProfileOnly & MFAVerified]

    def patch(self, request):
        serializer = CancelarDespachoSerializer(data=request.query_params)
        if not serializer.is_valid():
            raise BadRequestException(detail=serializer.errors)

        despacho = get_object_or_404(Despacho, id=serializer.validated_data['cancel'])

        if despacho.estado in (Despacho.FINALIZADO, Despacho.CANCELADO):
            raise ConflictException(detail="El despacho no puede ser cancelado en su estado actual.")

        despacho_personal = DespachoPersonal.objects.filter(despacho=despacho).select_related('grupo').first()
        grupo_id = despacho_personal.grupo.id if despacho_personal else None

        log_data = {
            "rut": request.user.rut,
            "user_id": request.user.id,
            "despacho_id": despacho.id,
            "grupo_id": grupo_id,
        }

        with transaction.atomic():
            change_despacho_status(type=Despacho.CANCELADO, despacho=despacho)
            transaction.on_commit(lambda: cancelar_despacho_log.delay(data=log_data))
            if grupo_id:
                transaction.on_commit(lambda: notificacion.delay(
                    type=Despacho.CANCELADO, grupo_id=grupo_id, despacho_id=despacho.id
                ))

        return Response({}, status=status.HTTP_200_OK)


# API para obtener TODOS Los despachos sin necesidad de incluir al usuario per se
class AllDespachos(APIView):
    http_method_names = ['get']
    permission_classes = [MFAVerified & ControlProfileOnly]
    def get(self, request):
        r = all_despachos(request.query_params)
        return Response(r, status=status.HTTP_200_OK)

# API para retornar el despacho asignado al USUARIO LOGEADO AL MOMENTO DE HACER LA SOLICITUD, diferenciar de arriba que retorna todos los despachos
class DespachoASolicitudUsuario(APIView):
    http_method_names = ['get']
    permission_classes = [MFAVerified]
    def get(self, request):
        r = solicitud_usuario(request.user)
        return Response(r, status=status.HTTP_200_OK)
       


# API para retornar las atenciones, recibe parámetros a través de URL
class RetornarAtencionAPI(APIView):
    permission_classes = [MFAAndClinicalProfile]
    http_method_names = ['get']
    def get(self, request):
        if request.query_params:
            r = atencion_with_query(request.query_params, request.user)
            return Response({'success':f'{r}'}, status=status.HTTP_200_OK)
        if request.user.rol.nombre_rol != 'control':
            raise ForbiddenException(detail="Solo el personal de control puede listar todas las atenciones")
        r = atencion_noquery()
        return Response(r, status=status.HTTP_200_OK)

class FHIR(APIView):
    permission_classes = [ControlProfileOnly & MFAVerified]
    def get(self, request):
        try:
            data  = export_hl7(request.query_params.get('id'))
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class CambiarEstadoAmbulancia(APIView):
    http_method_names = ['patch']
    permission_classes = [ControlProfileOnly & MFAVerified]
    def patch(self, request):
        if cambiar_estado.cambiar_estado(request.query_params, request.user.rut):
            return Response({}, status=status.HTTP_200_OK)


class VerificarDocumentoAPI(APIView):
    from ims_backend.serializers import VerificarDocumentoSerializer
    http_method_names = ['get']
    permission_classes = [MFAVerified]

    def get(self, request):
        from ims_backend.models import Documento
        from ims_backend.aws_package.s3 import s3_client
        from ims_backend.toolbox.customencoder import CustomEncoder
        from backend_config.settings import AWS_BUCKET_NAME
        import rustjson, base64, json as _json

        serializer = self.VerificarDocumentoSerializer(data=request.query_params)
        if not serializer.is_valid():
            raise BadRequestException(detail=serializer.errors)

        hash_input = serializer.validated_data["hash"]
        firma_input = serializer.validated_data.get("firma")

        try:
            doc = Documento.objects.select_related("atencion").get(archivo_hash=hash_input)
        except Documento.DoesNotExist:
            raise NotFoundException(detail="No existe un documento con ese hash.")

        try:
            raw_json = s3_client.get_object(
                Bucket=AWS_BUCKET_NAME, Key=doc.archivo_s3_key
            )["Body"].read()

            # .sig was uploaded as base64 text, not raw bytes
            stored_sig_b64 = s3_client.get_object(
                Bucket=AWS_BUCKET_NAME, Key=doc.firma_s3_key
            )["Body"].read()
            stored_sig_bytes = base64.b64decode(stored_sig_b64)
        except Exception:
            raise InternalServerException(detail="Error al descargar el documento desde S3.")

        try:
            # Strip Hash and Firma — they were added AFTER the original hash was computed
            document = _json.loads(raw_json)
            document.pop("Hash", None)
            document.pop("Firma", None)
            clean_bytes = _json.dumps(
                document, sort_keys=True, ensure_ascii=False, cls=CustomEncoder
            ).encode("utf-8")

            computed_hash_bytes, computed_sig_bytes = rustjson.data(clean_bytes)
        except Exception:
            raise InternalServerException(detail="Error al recomputar el hash del documento.")

        hash_ok  = computed_hash_bytes.hex() == hash_input
        sig_s3_ok = computed_sig_bytes == stored_sig_bytes

        result = {
            "hash":            hash_input,
            "hash_valido":     hash_ok,
            "firma_s3_valida": sig_s3_ok,
            "atencion_id":     doc.atencion_id,
            "creado_en":       doc.created_at,
        }

        if firma_input:
            try:
                firma_bytes = base64.b64decode(firma_input)
                result["firma_parametro_valida"] = (firma_bytes == stored_sig_bytes)
            except Exception:
                result["firma_parametro_valida"] = False

        result["valido"] = hash_ok and sig_s3_ok
        return Response(result, status=status.HTTP_200_OK)


class SenalAPI(APIView):
    http_method_names = ['post']
    permission_classes = [MFAAndFieldStaff]

    def post(self, request):
        from ims_backend.toolbox.Senales_package.signal_handler import handle_signal
        tipo = request.query_params.get('type')
        raw_did = request.query_params.get('despacho_id')
        despacho_id = int(raw_did) if raw_did and raw_did.isdigit() else None
        with transaction.atomic():
            handle_signal(tipo, request.data, request.user, despacho_id=despacho_id)
        return Response({}, status=status.HTTP_200_OK)