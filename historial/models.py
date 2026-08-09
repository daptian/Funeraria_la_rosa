from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
# Create your models here.

class AccionHistorial(models.Model):
    # Tipos de acciones
    TIPOS_ACCION = [
        ('crear', 'Crear'),
        ('actualizar', 'Actualizar'),
        ('eliminar', 'Eliminar'),
        ('generar', 'Generar'),
        ('aprobar', 'Aprobar'),
        ('rechazar', 'Rechazar'),
        ('login', 'Login'),
        ('logout', 'Logout'),
    ]
    
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    tipo_accion = models.CharField(max_length=20, choices=TIPOS_ACCION)
    modelo = models.CharField(max_length=100)  # Nombre del modelo (Ej: 'Pago', 'Usuario', 'Contrato')
    objeto_id = models.IntegerField(null=True, blank=True)  # ID del objeto afectado
    objeto_descripcion = models.CharField(max_length=255)  # Descripción del objeto (Ej: 'Juan Pérez', 'Contrato #123')
    detalles = models.TextField(blank=True, null=True)  # Detalles adicionales (JSON)
    fecha = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        db_table = 'AccionHistorial'
        ordering = ['-fecha']
        verbose_name = 'Acción del Historial'
        verbose_name_plural = 'Acciones del Historial'
        indexes = [
            models.Index(fields=['-fecha']),
            models.Index(fields=['usuario', '-fecha']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_accion_display()} - {self.modelo} - {self.fecha.strftime('%d/%m/%Y %H:%M')}"
