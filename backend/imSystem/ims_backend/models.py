from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import date
from django.conf import settings
class RolPersonal(models.Model):
    nombre_rol = models.CharField(max_length=50)  # medico, tens, chofer, control

    def __str__(self):
        return self.nombre_rol

class CategoriaInsumo(models.Model):
    categoria = models.CharField(max_length=100,null=True, blank=True)
    def __str__(self):
        return self.categoria
    
class GrupoPersonal(models.Model):
    nombre_grupo = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre_grupo


class Personal(AbstractUser):
    totp_secret = models.CharField(max_length=32, blank=True, null=True)
    rut = models.CharField(max_length=12, unique=True)
    rol= models.ForeignKey(RolPersonal, on_delete=models.PROTECT, null=True)
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    class Meta:
        indexes = [
            models.Index(fields=['rut']),
        ]

    def __str__(self):
        rol = self.rol.nombre_rol if self.rol else 'Sin rol'
        return f"{self.get_full_name()} ({rol})"


class SuscritosAGrupo(models.Model):
    grupo = models.ForeignKey(GrupoPersonal, on_delete=models.PROTECT, related_name="grupo_nombre")
    personal = models.ForeignKey(Personal, on_delete=models.PROTECT, related_name="grupo_personal")
    fecha_entrada = models.DateTimeField(auto_now_add=True)
    fecha_salida = models.DateTimeField(null= True, blank=True, help_text="Es null cuando esta activo en el grupo")
    class Meta:
        indexes = [
            models.Index(fields = [ 'grupo', 'fecha_entrada']),
            models.Index(fields= ['grupo', 'fecha_salida']),
            models.Index(fields= ['grupo','personal'])
        ]
#workflow test
class Paciente(models.Model):
    rut = models.CharField(max_length=12, unique=True)
    nombre_completo = models.CharField(max_length=255)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    direccion = models.CharField(max_length=255)
    condicion_paciente = models.TextField(null=True, blank=True)
    telefono = models.CharField(max_length=12, null=True, blank=True)
    comuna = models.CharField(max_length=30, blank=True, null=True)
    @property
    def edad(self):
        hoy = date.today()
        return hoy.year - self.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )

    def __str__(self):
        return self.nombre_completo


class Ambulancia(models.Model):
    ESTADOS = [
        ('disponible', 'Disponible'),
        ('en_despacho', 'En despacho'),
        ('mantencion', 'Mantención'),
        ('fuera_servicio', 'Fuera de servicio'),
    ]

    patente = models.CharField(max_length=10, unique=True)
    modelo = models.CharField(max_length=100)
    estado_disponibilidad = models.CharField(max_length=50, choices=ESTADOS, default='disponible')

    def __str__(self):
        return f"{self.modelo} - {self.patente}"

class InsumoMedico(models.Model):
    nombre_insumo = models.CharField(max_length=100)
    categoria = models.ForeignKey(CategoriaInsumo, on_delete=models.PROTECT, related_name="insumo_categoria", null=True)

    class Meta:
        indexes = [
            models.Index(fields=['nombre_insumo']),
        ]

    def __str__(self):
        return self.nombre_insumo

class UnidadMedidaInsumo(models.Model):
    unit = models.CharField(max_length=20)
    

class Despacho(models.Model):
    RECIBIDO = 'recibido'
    ASIGNADO = 'asignado'
    FINALIZADO = 'finalizado'
    CANCELADO = 'cancelado'
    PROGRAMADO = 'programado'
    EMERGENCIA = 'emergencia'
    ESTADOS = [
        (RECIBIDO, 'Recibido en control'),
        (ASIGNADO, 'Asignado a equipo'),
        (FINALIZADO, 'Finalizado'),
        (CANCELADO, 'Cancelado'),
        (PROGRAMADO, 'Despacho Programado'),
        (EMERGENCIA, 'Despacho Emergencia')
    ]

    direccion_origen = models.CharField(max_length=255)
    direccion_destino = models.CharField(max_length=255, blank=True)
    descripcion_llamado = models.TextField(blank=True)

    ambulancia = models.ForeignKey(Ambulancia, on_delete=models.PROTECT, null=True, blank=True)
    creado_por = models.ForeignKey(
        Personal,
        on_delete=models.PROTECT,
        related_name='despachos_creados',
        help_text="Usuario de control que creó el despacho",
        null=True,
        blank=True
    )#SE RELLENA AL MOMENTO DE CREAR EL DESPACHO ES AUTOMATICO TOMA EL USUAIRO MEDIANTE REQUEST.USER
    asignado_por = models.ForeignKey(
        Personal,
        on_delete=models.PROTECT,
        related_name='despachos_asignados',
        help_text="Usuario de control que asignó el despacho",
        null=True,
        blank=True
    )#SE RELLENA AL MOMENTO DE ASIGNARLE UN DESPACHO A UN GRUPO NO EN LA CREACION DE UN DESPACHO 
    #ES AUTOMATICO TOMA EL USUARIO MEDIANTE REQUEST.USER

    estado = models.CharField(max_length=30, choices=ESTADOS, default='recibido')
    fecha_programada = models.DateTimeField(null=True, blank=True)
    fecha_llamado = models.DateTimeField(auto_now_add=True)
    fecha_asignacion = models.DateTimeField(null=True, blank=True)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)
    paciente = models.ForeignKey(Paciente, related_name='despacho_paciente', null=True, on_delete=models.PROTECT)
    #Acá se asigna al paciente al momento de crear el despacho
    class Meta:
        indexes = [
            models.Index(fields=['estado', 'fecha_llamado']),
        ]

    def __str__(self):
        return f"Despacho {self.id} - {self.estado}"


class DespachoPersonal(models.Model):
    despacho = models.ForeignKey(Despacho, on_delete=models.CASCADE, related_name='equipo')
    grupo = models.ForeignKey(GrupoPersonal, on_delete=models.PROTECT)
    asignado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['despacho', 'grupo']

    def __str__(self):
        return f"{self.grupo} en Despacho {self.despacho.id}"


class Atencion(models.Model):
    FINALIZADA = 'finalizada'
    REGISTRADA = 'registrada'
    CREADA = 'creada'
    ESTADOS = [
        (REGISTRADA, 'Atencion registrada en S3 y BD'),
        (CREADA, 'Atencion creada, pero sin existir en S3')
    ]
    ambulancia = models.ForeignKey(Ambulancia, on_delete=models.PROTECT)
    despacho = models.OneToOneField(
        Despacho,
        on_delete=models.PROTECT,
        related_name='atencion',
        null=True,
        blank=True
    )
    hora_salida = models.DateTimeField()
    hora_llegada = models.DateTimeField(null=True, blank=True)

    sello_electronico = models.TextField(blank=True, null=True, help_text="Hash de integridad")
    estado_sello = models.CharField(max_length=20, default="Pendiente")
    rut_registrador = models.ForeignKey(Personal, null=False, blank= False, on_delete=models.PROTECT, default='1')
    rut_receptor = models.CharField(max_length=12, null=True, blank=True, help_text="Si está en blanco fue recibido por la misma institución")
    def __str__(self):
        return f"Atención {self.id} - {self.despacho.paciente.nombre_completo if self.despacho 
                                       and self.despacho.paciente else 'Sin paciente'}"

class SignosVitales(models.Model):
    atencion = models.ForeignKey(Atencion, on_delete=models.CASCADE, related_name='signos_vitales')
    timestamp = models.DateTimeField(auto_now_add=True)
    presion_sistolica = models.IntegerField(null=True, blank=True)
    presion_diastolica = models.IntegerField(null=True, blank=True)
    frecuencia_cardiaca = models.IntegerField(null=True, blank=True)
    saturacion_oxigeno = models.IntegerField(null=True, blank=True)
    temperatura = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    fr = models.IntegerField(null=True, blank=True)
    fio2 = models.IntegerField(null=True, blank=True)
    hgt = models.IntegerField(null=True, blank=True)
    gcs = models.IntegerField(null=True, blank=True)
    eva = models.IntegerField(null=True, blank=True)
    hora = models.CharField(max_length=4, null=False, blank=False, default="0000")
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Signos Atencion {self.atencion.id} - {self.timestamp}"


class PresentacionInsumo(models.Model):
    insumo = models.ForeignKey(InsumoMedico, on_delete=models.PROTECT, related_name="presentacion_insumo")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2) #200 MG X ej
    unidad_medida = models.ForeignKey(UnidadMedidaInsumo, on_delete=models.PROTECT, related_name="presentacion_um")
class DetalleInsumoAtencion(models.Model):
    atencion = models.ForeignKey(Atencion, on_delete=models.CASCADE)
    insumo = models.ForeignKey(PresentacionInsumo, on_delete=models.PROTECT, related_name="insumos_utilizados")
    observaciones = models.CharField(max_length=250, blank=True)
    cantidad_usada = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.insumo.insumo.nombre_insumo} en Atencion {self.atencion.id}"

class StockInsumo(models.Model):
    presentacion = models.ForeignKey(PresentacionInsumo, on_delete=models.PROTECT, related_name="stocks_presentacion")
    ambulancia = models.ForeignKey(Ambulancia, on_delete=models.PROTECT, related_name="stocks_ambulancia")
    stock = models.IntegerField(default=0)

    class Meta:
        unique_together = ['presentacion', 'ambulancia']

class Documento(models.Model):
    archivo_s3_key = models.CharField(max_length=500, help_text="Ruta del archivo")
    archivo_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        editable=False
    )
    firma_s3_key = models.CharField(max_length=500, blank=True, help_text="Ruta de la firma .sig en S3")
    atencion = models.ForeignKey(Atencion, on_delete=models.PROTECT, related_name='documentos', null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"Documento {self.id} - {self.archivo_hash[:16]}..."


class Notificacion(models.Model):
    TIPOS = [
        ('despacho', 'Nuevo despacho'),
        ('reasignacion', 'Reasignación'),
        ('alerta_stock', 'Stock bajo mínimo'),
        ('sistema', 'Sistema'),
    ]

    destinatario = models.ForeignKey(GrupoPersonal, on_delete=models.CASCADE, related_name='notificaciones')
    tipo = models.CharField(max_length=30, choices=TIPOS)
    titulo = models.CharField(max_length=255)
    mensaje = models.TextField()
    url_embebida = models.CharField(max_length=500, blank=True, help_text="Link a Google Maps u otro")

    despacho = models.ForeignKey(Despacho, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['destinatario']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif {self.tipo} para {self.destinatario}"

#UNUSED
class TicketCredencial(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('en_revision', 'En revisión'),
        ('resuelto', 'Resuelto'),
        ('rechazado', 'Rechazado'),
    ]

    solicitante = models.ForeignKey(Personal, on_delete=models.CASCADE, related_name='tickets_credencial')
    motivo = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')

    resuelto_por = models.ForeignKey(
        Personal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets_resueltos',
        help_text="Usuario control que resolvió el ticket"
    )
    observaciones_resolucion = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['estado', 'created_at']),
        ]

    def __str__(self):
        return f"Ticket #{self.id} - {self.solicitante} - {self.estado}"


class LogAuditoria(models.Model):
    TIPOS = [
        ('atencion', 'Atención'),
        ('inventario', 'Inventario'),
        ('ambulancia', 'Ambulancia'),
        ('despacho', 'Despacho'),
        ('grupo','Grupo'),
        ('paciente','Paciente')
    ]
    tipo = models.CharField(max_length=20, choices=TIPOS, default="placeholder")
    atencion = models.ForeignKey(Atencion, on_delete=models.PROTECT, null=True, blank=True)
    usuario = models.ForeignKey(Personal, on_delete=models.PROTECT, related_name='logs')
    rut_usuario = models.CharField(max_length=12)
    descripcion = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

class DeviceToken(models.Model):
    device_token = models.CharField(max_length=255, null=False, blank=False, unique=True)
    usuario = models.ForeignKey(Personal, related_name="token_personal", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"device token: {self.device_token}, user: {self.usuario}, created at: {self.created_at}"
    
class PreInforme(models.Model):
    atencion = models.OneToOneField(Atencion,on_delete=models.CASCADE, related_name="preinforme_atencion")
    pre_informe= models.CharField(max_length=250, null=True, blank=True)
    motivo_llamado = models.CharField(max_length=150, null=True, blank=True)
    estado_paciente = models.CharField(max_length=150, null=True, blank=True)

class Cronologia(models.Model):
    atencion = models.OneToOneField(Atencion, on_delete=models.CASCADE, related_name="crono_atencion")
    hora_llamada = models.CharField(max_length=4, null=True, blank=True)
    despacho_movil = models.CharField(max_length=4, null=True, blank=True)
    llegada_qth1  = models.CharField(max_length=4, null=True, blank=True)
    salida_qth1  = models.CharField(max_length=4, null=True, blank=True)
    llegada_qth2  = models.CharField(max_length=4, null=True, blank=True)
    salida_qth2  = models.CharField(max_length=4, null=True, blank=True)
    categoria = models.CharField(max_length=2, null=False, blank=False)