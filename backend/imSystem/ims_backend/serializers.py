# ---- DJANGO DRF SERIALIZERS ----
from rest_framework import serializers

# ---- MODELS ----
from .models import (
    Paciente, Ambulancia, Personal, Despacho,
    Atencion, GrupoPersonal, SuscritosAGrupo, SignosVitales, PreInforme,
    Cronologia
)

class PersonalSerializer(serializers.ModelSerializer):
    rol_nombre = serializers.CharField(source='rol.nombre_rol', read_only=True, default=None)

    class Meta:
        model = Personal
        fields = ['id', 'username', 'first_name', 'last_name', 'rut', 'is_active', 'rol_nombre']
        read_only_fields = ['username', 'rol_nombre']


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
    insumo_id = serializers.IntegerField()
    dosis=serializers.DecimalField(max_digits=10, decimal_places=1)
    observaciones = serializers.CharField(max_length=255, required=False)
class PayloadSerializer(serializers.Serializer):
    despacho = DespachoAtencionSerializer()
    signos_vitales = SignosVitalesSerializer(many=True)
    preinforme = PreInformeSerializer()
    cronologia = CronologiaSerializer()
    insumos_utilizados = InsumoUtilizadoSerializer(many=True)

class AuthenticationSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    totp_code = serializers.CharField()
class InsumoIdSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    ambulancia_id = serializers.IntegerField()