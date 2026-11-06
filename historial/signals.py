import json

from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from client.models import Titular
from payment.models import Pago, Reporte
from .models import AccionHistorial


def obtener_ip_usuario(request):
    """Obtiene la IP del usuario desde la request, si está disponible."""
    if not request:
        return None
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _registrar_accion(*, actor=None, tipo, modelo, objeto, descripcion,
                      detalles=None, request=None):
    AccionHistorial.objects.create(
        usuario=actor,
        tipo_accion=tipo,
        modelo=modelo,
        objeto_id=getattr(objeto, 'pk', None),
        objeto_descripcion=descripcion,
        detalles=json.dumps(detalles or {}, default=str),
        ip_address=obtener_ip_usuario(request),
    )


def _datos_publicos_usuario(user):
    """Campos auditables de User; deliberadamente excluye la contraseña."""
    return {
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
    }


@receiver(pre_save, sender=User)
def guardar_estado_anterior_usuario(sender, instance, **kwargs):
    if not instance.pk:
        instance._estado_anterior_auditoria = None
        return
    anterior = sender.objects.filter(pk=instance.pk).first()
    instance._estado_anterior_auditoria = (
        _datos_publicos_usuario(anterior) if anterior else None
    )


@receiver(post_save, sender=User)
def registrar_usuario_guardado(sender, instance, created, **kwargs):
    actual = _datos_publicos_usuario(instance)
    anterior = getattr(instance, '_estado_anterior_auditoria', None)
    if created:
        tipo = 'crear'
        detalles = actual
    elif anterior is not None:
        cambios = {
            campo: {'anterior': anterior[campo], 'nuevo': valor}
            for campo, valor in actual.items()
            if anterior.get(campo) != valor
        }
        if not cambios:
            return
        tipo = 'actualizar'
        detalles = cambios
    else:
        return

    _registrar_accion(
        actor=instance,
        tipo=tipo,
        modelo='Usuario',
        objeto=instance,
        descripcion=f"Usuario: {instance.get_full_name() or instance.username}",
        detalles=detalles,
    )


@receiver(post_delete, sender=User)
def registrar_usuario_eliminado(sender, instance, **kwargs):
    _registrar_accion(
        actor=None,
        tipo='eliminar',
        modelo='Usuario',
        objeto=instance,
        descripcion=f"Usuario: {instance.get_full_name() or instance.username}",
        detalles=_datos_publicos_usuario(instance),
    )


@receiver(user_logged_in)
def registrar_inicio_sesion(sender, request, user, **kwargs):
    _registrar_accion(
        actor=user,
        tipo='login',
        modelo='Usuario',
        objeto=user,
        descripcion=f"Inicio de sesión: {user.username}",
        request=request,
    )


@receiver(user_logged_out)
def registrar_cierre_sesion(sender, request, user, **kwargs):
    _registrar_accion(
        actor=user,
        tipo='logout',
        modelo='Usuario',
        objeto=user,
        descripcion=f"Cierre de sesión: {user.username}" if user else 'Cierre de sesión',
        request=request,
    )


@receiver(pre_save, sender=Titular)
def guardar_estado_anterior_titular(sender, instance, **kwargs):
    if not instance.pk:
        instance._estado_anterior_auditoria = None
        return
    anterior = sender.objects.filter(pk=instance.pk).first()
    instance._estado_anterior_auditoria = (
        {campo: getattr(anterior, campo) for campo in (
            'cedula', 'numero_contrato', 'nombre', 'apellido', 'sexo', 'edad',
            'estado_civil', 'ocupacion', 'direccion', 'telefono',
            'fecha_ingreso', 'plan_activo',
        )} if anterior else None
    )


@receiver(post_save, sender=Titular)
def registrar_titular_guardado(sender, instance, created, **kwargs):
    campos = (
        'cedula', 'numero_contrato', 'nombre', 'apellido', 'sexo', 'edad',
        'estado_civil', 'ocupacion', 'direccion', 'telefono',
        'fecha_ingreso', 'plan_activo',
    )
    actual = {campo: getattr(instance, campo) for campo in campos}
    anterior = getattr(instance, '_estado_anterior_auditoria', None)
    if created:
        tipo = 'crear'
        detalles = actual
    elif anterior is not None:
        detalles = {
            campo: {'anterior': anterior[campo], 'nuevo': valor}
            for campo, valor in actual.items()
            if anterior.get(campo) != valor
        }
        if not detalles:
            return
        tipo = 'actualizar'
    else:
        return

    _registrar_accion(
        tipo=tipo,
        modelo='Titular',
        objeto=instance,
        descripcion=f"Titular: {instance.nombre} {instance.apellido}",
        detalles=detalles,
    )


@receiver(post_delete, sender=Titular)
def registrar_titular_eliminado(sender, instance, **kwargs):
    _registrar_accion(
        tipo='eliminar',
        modelo='Titular',
        objeto=instance,
        descripcion=f"Titular: {instance.nombre} {instance.apellido}",
        detalles={
            'cedula': instance.cedula,
            'numero_contrato': instance.numero_contrato,
        },
    )


# SIGNALS PARA PAGO
@receiver(post_save, sender=Pago)
def registrar_pago_creado(sender, instance, created, **kwargs):
    if created:
        _registrar_accion(
            actor=getattr(instance, 'usuario', None),
            tipo='crear',
            modelo='Pago',
            objeto=instance,
            descripcion=f"Pago #{instance.id} - ${instance.monto_total_a_pagar}",
            detalles={
                'monto': str(instance.monto_total_a_pagar),
                'estado': getattr(instance, 'estado', 'pendiente'),
            },
        )


@receiver(post_delete, sender=Pago)
def registrar_pago_eliminado(sender, instance, **kwargs):
    _registrar_accion(
        tipo='eliminar',
        modelo='Pago',
        objeto=instance,
        descripcion=f"Pago #{instance.id} - ${instance.monto_total_a_pagar}",
        detalles={'razon': 'Eliminado del sistema'},
    )


# SIGNALS PARA REPORTE
@receiver(post_save, sender=Reporte)
def registrar_reporte_generado(sender, instance, created, **kwargs):
    if created:
        tipo_reporte = 'diario' if instance.diario else (
            'semanal' if instance.semanal else 'mensual'
        )
        _registrar_accion(
            tipo='generar',
            modelo='Reporte',
            objeto=instance,
            descripcion=f"Reporte {tipo_reporte} - ${instance.valor_total_recaudado}",
            detalles={
                'tipo': tipo_reporte,
                'monto': str(instance.valor_total_recaudado),
                'fecha': str(instance.fecha_generacion),
            },
        )
