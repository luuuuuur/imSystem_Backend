# ---- DJANGO DRF SERIALIZERS ----
from rest_framework import serializers

# ---- MODELS ----
from .models import (
    Paciente, Ambulancia, Personal, Despacho,
    Atencion, GrupoPersonal, SuscritosAGrupo
)

class PersonalSerializer(serializers.ModelSerializer):
    rol_nombre = serializers.CharField(source='rol.nombre_rol', read_only=True)

    class Meta:
        model = Personal
        fields = ['id', 'username', 'first_name', 'last_name', 'rut', 'is_active', 'rol_nombre']
        read_only_fields = ['username', 'rol_nombre']


class PacienteSerializer(serializers.ModelSerializer):
    full_name  = serializers.CharField(source='nombre_completo')
    date_birth = serializers.DateField(source='fecha_nacimiento')

    class Meta:
        model = Paciente
        fields = [
            'id', 'rut', 'full_name', 'date_birth',
            'direccion', 'condicion_paciente', 'telefono', 'comuna'
        ]



class DespachoSerializer(serializers.ModelSerializer):
    d_o      = serializers.CharField(source='direccion_origen')
    d_d      = serializers.CharField(source='direccion_destino',    required=False, allow_blank=True, default='')
    d_llamado = serializers.CharField(source='descripcion_llamado', required=False, allow_blank=True, default='')

    class Meta:
        model  = Despacho
        fields = ['id', 'd_o', 'd_d', 'd_llamado', 'estado', 'ambulancia', 'creado_por', 'asignado_por']
        read_only_fields = ['estado', 'creado_por', 'asignado_por', 'ambulancia']


class AsignarDespachoSerializer(serializers.Serializer):
    amb_id   = serializers.IntegerField()
    d_id     = serializers.IntegerField()
    grupo_id = serializers.IntegerField()

class AmbulanciaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Ambulancia
        fields = '__all__'



class AtencionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Atencion
        fields = '__all__'
        read_only_fields = ['sello_electronico', 'estado_sello']


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
    group_id    = serializers.IntegerField()
    personal_id = serializers.IntegerField()
