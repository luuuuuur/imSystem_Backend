from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import date


class RolPersonal(models.Model):
    nombre_rol = models.CharField(max_length=50)  # medico, tens, chofer, control

    def __str__(self):
        return self.nombre_rol


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

class Paciente(models.Model):
    rut = models.CharField(max_length=12, unique=True)
    nombre_completo = models.CharField(max_length=255)
    fecha_nacimiento = models.DateField()
    direccion = models.CharField(max_length=255)
    condicion_paciente = models.TextField()
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
    stock_total = models.IntegerField()
    stock_minimo = models.IntegerField(default=0)
    unidad_medida = models.CharField(max_length=20)  # mg, ml, unidades
    tipo = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre_insumo


class Despacho(models.Model):
    ESTADOS = [
        ('recibido', 'Recibido en control'),
        ('asignado', 'Asignado a equipo'),
        ('en_ruta_paciente', 'En ruta al paciente'),
        ('paciente_recogido', 'Paciente recogido'),
        ('en_ruta_hospital', 'En ruta al hospital'),
        ('finalizado', 'Finalizado'),
        ('cancelado', 'Cancelado'),
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
    )
    asignado_por = models.ForeignKey(
        Personal,
        on_delete=models.PROTECT,
        related_name='despachos_asignados',
        help_text="Usuario de control que asignó el despacho",
        null=True,
        blank=True
    )

    estado = models.CharField(max_length=30, choices=ESTADOS, default='recibido')
    fecha_llamado = models.DateTimeField(auto_now_add=True)
    fecha_asignacion = models.DateTimeField(null=True, blank=True)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)

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
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE)
    ambulancia = models.ForeignKey(Ambulancia, on_delete=models.PROTECT)
    despacho = models.OneToOneField(
        Despacho,
        on_delete=models.PROTECT,
        related_name='atencion',
        null=True,
        blank=True
    )

    direccion_despacho = models.CharField(max_length=255)
    hora_salida = models.DateTimeField()
    hora_llegada = models.DateTimeField(null=True, blank=True)

    sello_electronico = models.TextField(blank=True, null=True, help_text="Hash de integridad")
    estado_sello = models.CharField(max_length=20, default="Pendiente")

    def __str__(self):
        return f"Atención {self.id} - {self.paciente.nombre_completo}"


class SignosVitales(models.Model):
    atencion = models.ForeignKey(Atencion, on_delete=models.CASCADE, related_name='signos_vitales')
    timestamp = models.DateTimeField(auto_now_add=True)
    presion_sistolica = models.IntegerField(null=True, blank=True)
    presion_diastolica = models.IntegerField(null=True, blank=True)
    frecuencia_cardiaca = models.IntegerField(null=True, blank=True)
    saturacion_oxigeno = models.IntegerField(null=True, blank=True)
    temperatura = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Signos Atencion {self.atencion.id} - {self.timestamp}"


class DetalleInsumoAtencion(models.Model):
    atencion = models.ForeignKey(Atencion, on_delete=models.CASCADE, related_name='insumos_utilizados')
    insumo = models.ForeignKey(InsumoMedico, on_delete=models.PROTECT)
    dosis = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.insumo.nombre_insumo} en Atencion {self.atencion.id}"


class Documento(models.Model):
    archivo_s3_key = models.CharField(max_length=500, help_text="Ruta del archivo dentro del bucket S3")
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
    atencion = models.ForeignKey(
        Atencion,
        on_delete=models.PROTECT,
        related_name='logs',
        help_text="Atención a la que pertenece esta acción"
    )
    usuario = models.ForeignKey(
        Personal,
        on_delete=models.PROTECT,
        related_name='acciones',
        help_text="Personal que ejecutó la acción"
    )
    rut_usuario = models.CharField(
        max_length=12,
        help_text="RUT duplicado para preservar trazabilidad si el usuario se elimina"
    )
    descripcion = models.TextField(
        help_text="Ej: 'Administró 500mg de paracetamol vía oral'"
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['atencion', 'timestamp']),
            models.Index(fields=['usuario', 'timestamp']),
        ]
        ordering = ['timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.rut_usuario} - {self.descripcion[:50]}"