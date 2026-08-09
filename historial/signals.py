from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import AccionHistorial
from client.models import Titular
from payment.models import Pago, Reporte
import json

def obtener_ip_usuario(request):
    """Obtiene la IP del usuario desde la request"""
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
    return None

# SIGNALS PARA PAGO
@receiver(post_save, sender=Pago)
def registrar_pago_creado(sender, instance, created, **kwargs):
    """Registra cuando se crea o actualiza un pago"""
    if created:
        AccionHistorial.objects.create(
            usuario=instance.usuario if hasattr(instance, 'usuario') else None,
            tipo_accion='crear',
            modelo='Pago',
            objeto_id=instance.id,
            objeto_descripcion=f"Pago #{instance.id} - ${instance.monto_total_a_pagar}",
            detalles=json.dumps({
                'monto': str(instance.monto_total_a_pagar),
                'estado': instance.estado if hasattr(instance, 'estado') else 'pendiente'
            })
        )

@receiver(post_delete, sender=Pago)
def registrar_pago_eliminado(sender, instance, **kwargs):
    """Registra cuando se elimina un pago"""
    AccionHistorial.objects.create(
        usuario=None,
        tipo_accion='eliminar',
        modelo='Pago',
        objeto_id=instance.id,
        objeto_descripcion=f"Pago #{instance.id} - ${instance.monto_total_a_pagar}",
        detalles=json.dumps({'razon': 'Eliminado del sistema'})
    )

# SIGNALS PARA USUARIO
@receiver(post_save, sender=Titular)
def registrar_usuario_creado(sender, instance, created, **kwargs):
    """Registra cuando se crea un usuario"""
    if created:
        AccionHistorial.objects.create(
            usuario=None,
            tipo_accion='crear',
            modelo='Titular',
            objeto_id=instance.id,
            objeto_descripcion=f"Nuevo Titular: {instance.nombre} {instance.apellido}",
            detalles=json.dumps({
                'Titular': instance.nombre,
            })
        )

@receiver(post_delete, sender=User)
def registrar_usuario_eliminado(sender, instance, **kwargs):
    """Registra cuando se elimina un usuario"""
    AccionHistorial.objects.create(
        usuario=None,
        tipo_accion='eliminar',
        modelo='Usuario',
        objeto_id=instance.id,
        objeto_descripcion=f"Usuario: {instance.get_full_name() or instance.username}",
    )

# SIGNALS PARA REPORTE
@receiver(post_save, sender=Reporte)
def registrar_reporte_generado(sender, instance, created, **kwargs):
    """Registra cuando se genera un reporte"""
    if created:
        tipo = 'diario' if instance.diario else ('semanal' if instance.semanal else 'mensual')
        AccionHistorial.objects.create(
            tipo_accion='generar',
            modelo='Reporte',
            objeto_id=instance.id,
            objeto_descripcion=f"Reporte {tipo} - ${instance.valor_total_recaudado}",
            detalles=json.dumps({
                'tipo': tipo,
                'monto': str(instance.valor_total_recaudado),
                'fecha': str(instance.fecha_generacion)
            })
        )

# @receiver(post_save, sender=Contrato)
# def registrar_contrato_creado(sender, instance, created, **kwargs):
#     """Registra cuando se crea o actualiza un contrato"""
#     if created:
#         AccionHistorial.objects.create(
#             usuario=instance.usuario if hasattr(instance, 'usuario') else None,
#             tipo_accion='crear',
#             modelo='Contrato',
#             objeto_id=instance.id,
#             objeto_descripcion=f"Contrato #{instance.id}",
#             detalles=json.dumps({
#                 'titular': str(instance.titular) if hasattr(instance, 'titular') else 'N/A'
#             })
#         )

# @receiver(post_delete, sender=Contrato)
# def registrar_contrato_eliminado(sender, instance, **kwargs):
#     """Registra cuando se elimina un contrato"""
#     AccionHistorial.objects.create(
#         tipo_accion='eliminar',
#         modelo='Contrato',
#         objeto_id=instance.id,
#         objeto_descripcion=f"Contrato #{instance.id}",
#     )