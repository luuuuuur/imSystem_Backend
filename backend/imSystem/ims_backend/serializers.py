# ---- DJANGO DRF SERIALIZERS ----

from rest_framework import serializers

# ---- MODELS ----
from .models import (
    Ambulancia, Personal, Atencion, GrupoPersonal, SuscritosAGrupo, SignosVitales, PreInforme,
    Cronologia, LogAuditoria, Despacho
)


class PersonalSerializer(serializers.ModelSerializer):
    rol_nombre = serializers.CharField(source='rol.nombre_rol', read_only=True, default=None)

    class Meta:
        model = Personal
        fields = ['id', 'username', 'first_name', 'last_name', 'rut', 'is_active', 'rol_nombre', 'last_login']
        read_only_fields = ['username', 'rol_nombre', 'last_login']

class LogAuditoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model= LogAuditoria
        fields=["id","tipo", "atencion_id", "usuario", "rut_usuario", "descripcion", "timestamp"]

class DespachoListSerializer(serializers.ModelSerializer):
    paciente = serializers.SerializerMethodField()
    personal = serializers.SerializerMethodField()

    class Meta:
        model = Despacho
        fields = [
            "id", "estado", "direccion_origen", "direccion_destino",
            "descripcion_llamado", "fecha_llamado", "fecha_asignacion",
            "fecha_programada", "fecha_finalizacion",
            "ambulancia_id", "creado_por_id", "asignado_por_id",
            "paciente", "personal",
        ]

    def get_paciente(self, obj):
        if not obj.paciente:
            return None
        return {
            "nombre_completo": obj.paciente.nombre_completo,
            "rut": obj.paciente.rut,
            "fecha_nacimiento": obj.paciente.fecha_nacimiento
        }

    def get_personal(self, obj):
        equipo = getattr(obj, 'equipo_prefetch', [])
        if not equipo:
            return []
        miembros = getattr(equipo[0].grupo, 'miembros_activos', [])
        return [
            {
                "id": m.personal.id,
                "first_name": m.personal.first_name,
                "last_name": m.personal.last_name,
                "rut": m.personal.rut,
                "rol": m.personal.rol.nombre_rol if m.personal.rol else None,
            }
            for m in miembros
        ]
class PacienteSerializer(serializers.Serializer):
    rut              = serializers.CharField()
    nombre_completo  = serializers.CharField(required=False, default='')
    fecha_nacimiento = serializers.DateField(required=False, allow_null=True, default=None)
    direccion        = serializers.CharField(required=False, default='')
    condicion_paciente = serializers.CharField(required=False, default='')
    telefono         = serializers.CharField(required=False, default='')
    comuna           = serializers.CharField(required=False, default='')
class ParamPacienteSerializer(serializers.Serializer):
    rut = serializers.CharField(max_length=12, required=True)

class CreateDespachoSerializer(serializers.Serializer):
    direccion_origen     = serializers.CharField()
    direccion_destino      = serializers.CharField(required=False, allow_blank=True, default='No incluyó')
    descripcion_llamado = serializers.CharField(required=False, allow_blank=True, default='No incluyó')
    paciente_rut = serializers.CharField(write_only=True)

class AsignarDespachoSerializer(serializers.Serializer):
    is_emergency = serializers.BooleanField(required=False, default=False)
    amb_id   = serializers.IntegerField()
    despacho_id     = serializers.IntegerField()
    grupo_id = serializers.IntegerField()

class AmbulanciaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Ambulancia
        fields = '__all__'


class ObtenerDespachoSerializer(serializers.Serializer):
    despacho_id = serializers.IntegerField()

class AtencionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Atencion
        fields = '__all__'
        read_only_fields = ['sello_electronico', 'estado_sello']
#class PayloadSerializer(serializers.Serializer):


class MiembroGrupoSerializer(serializers.ModelSerializer):
    id         = serializers.IntegerField(source='personal.id',             read_only=True)
    first_name = serializers.CharField(source='personal.first_name',        read_only=True)
    last_name  = serializers.CharField(source='personal.last_name',         read_only=True)
    rut        = serializers.CharField(source='personal.rut',               read_only=True)
    rol        = serializers.CharField(source='personal.rol.nombre_rol',    read_only=True)

    class Meta:
        model  = SuscritosAGrupo
        fields = ['id', 'first_name', 'last_name', 'rut', 'rol']


class GrupoPersonalSerializer(serializers.ModelSerializer):
    miembros_activos = serializers.SerializerMethodField()

    class Meta:
        model  = GrupoPersonal
        fields = ['id', 'nombre_grupo', 'miembros_activos']

    def get_miembros_activos(self, obj):
        suscripciones_activas = SuscritosAGrupo.objects.filter(
            grupo=obj,
            fecha_salida=None
        ).select_related('personal', 'personal__rol')
        return MiembroGrupoSerializer(suscripciones_activas, many=True).data




class CrearGrupoSerializer(serializers.Serializer):
    nombre_grupo = serializers.CharField(max_length=100)

    personal = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        error_messages={'empty': 'Debe asignar al menos 1 persona al grupo'}
    )


class RemoverMiembroGrupo(serializers.Serializer):
    group_id    = serializers.IntegerField()
    personal_id = serializers.IntegerField()


class AgregarMiembroGrupo(serializers.Serializer):
    grupo_id    = serializers.IntegerField()
    personal_id = serializers.IntegerField()


class ParamSerializer(serializers.Serializer):
    group_id=serializers.IntegerField(required=True)
class ParamAtencionSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)
class SignosVitalesSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SignosVitales
        exclude = ['atencion','timestamp']

class PreInformeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreInforme
        exclude = ['atencion']

class CronologiaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cronologia
        exclude = ['atencion']

class DespachoAtencionSerializer(serializers.Serializer):
    despacho_id = serializers.IntegerField(required=True)
    ambulancia_id = serializers.IntegerField( required=True)
    hora_salida = serializers.DateTimeField(required=True)
    hora_llegada = serializers.DateTimeField(required=False)
class InsumoUtilizadoSerializer(serializers.Serializer):
    presentacion_id = serializers.IntegerField()
    cantidad_usada = serializers.IntegerField()
    observaciones = serializers.CharField(max_length=255, required=False)
class PayloadSerializer(serializers.Serializer):
    despacho = DespachoAtencionSerializer()
    signos_vitales = SignosVitalesSerializer(many=True)
    preinforme = PreInformeSerializer()
    cronologia = CronologiaSerializer()
    insumos_utilizados = InsumoUtilizadoSerializer(many=True)
    rut_receptor = serializers.CharField()
    paciente = PacienteSerializer()
class AuthenticationSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
class LoginSerializer(serializers.Serializer):
    totp_code=serializers.CharField()
class InsumoIdSerializer(serializers.Serializer):
    insumo_id = serializers.IntegerField()
class AmbulanciaSerializerID(serializers.Serializer):
    ambulancia_id = serializers.IntegerField()
class UpdateInsumoSerializer(serializers.Serializer):
    presentacion_id = serializers.IntegerField()
    ambulancia_id = serializers.IntegerField()
    cantidad = serializers.IntegerField()

class AddInsumoSerializer(serializers.Serializer):
    nombre_insumo = serializers.CharField()
    categoria_id = serializers.IntegerField()#FK
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=1)#DEL MEDICAMENTO: EJ 200/MG ETC...
    unidad_medida_id = serializers.IntegerField()#FK
    stock = serializers.IntegerField()#CANTIDAD QUE HAY
    ambulancia_id = serializers.IntegerField()#FK

class BulkAddInsumoSerializer(serializers.Serializer):
    items = AddInsumoSerializer(many=True)

class MoveItemSerializer(serializers.Serializer):
    presentacion_id = serializers.IntegerField()
    ambulancia_to_id = serializers.IntegerField()
    ambulancia_from_id = serializers.IntegerField()
    cantidad = serializers.IntegerField()

#se asume que el Despacho exista previamente
class ProgramarDespachoSerializer(serializers.Serializer):
    despacho_id = serializers.IntegerField()
    fecha_programada = serializers.DateTimeField()
    grupo_id= serializers.IntegerField()

class DeviceToken(serializers.Serializer):
    token = serializers.CharField()


class AddAmbulanciaSerializer(serializers.Serializer):
    patente = serializers.CharField(max_length=10)
    modelo  = serializers.CharField(max_length=100)
    estado_disponibilidad = serializers.ChoiceField(
        choices=Ambulancia.ESTADOS,
        default=Ambulancia.DISPONIBLE,
        required=False,
    )

class CambiarEstadoAmbulancia(serializers.Serializer):
    ambid = serializers.IntegerField()
    estado = serializers.ChoiceField(Ambulancia.ESTADOS)

class VerificarDocumentoSerializer(serializers.Serializer):
    hash  = serializers.CharField(max_length=64)
    firma = serializers.CharField(required=False)

class CancelarDespachoSerializer(serializers.Serializer):
    cancel = serializers.IntegerField()

class SenalOtroSerializer(serializers.Serializer):
    mensaje = serializers.CharField(max_length=500)

class SenalPatenteSerializer(serializers.Serializer):
    patente = serializers.CharField(max_length=10)