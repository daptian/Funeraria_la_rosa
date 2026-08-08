from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import Factura, Pago, Reporte
from dateutil.relativedelta import relativedelta
from django.utils import timezone


def calcular_proximo_pago(pago):
    fecha_base = (
            pago.proximo_pago
            or pago.titular.fecha_ingreso
            or timezone.localdate()
        )

    if not pago.proximo_pago:
        return fecha_base + relativedelta(months=1)

    return fecha_base + relativedelta(months=1)

def esta_vencido(pago):
    print(pago.fecha_ultimo_pago)
    print('Proximo pago:', pago.proximo_pago, 'Fecha actual:', timezone.localdate())
    if not pago.proximo_pago:
        return False
    return timezone.localdate() > pago.proximo_pago

def generar_factura_para_pago(pago_id):

    with transaction.atomic():

        pago = (
            Pago.objects
            .select_for_update()
            .select_related("titular")
            .get(pk=pago_id)
        )

        fecha_periodo = (
            pago.proximo_pago
            or pago.titular.fecha_ingreso
            or timezone.localdate()
        )

        factura, creada = Factura.objects.get_or_create(
            pago=pago,
            titular=pago.titular,
            periodo_anio=fecha_periodo.year,
            periodo_mes=fecha_periodo.month,
            defaults={
                "monto_mensual_tarifa": pago.monto_mensual_tarifa,
                "monto_cargos_unicos": pago.monto_cargos_unicos,
                "monto_total": pago.monto_total_a_pagar,
            }
        )

        if creada:
            pago.fecha_ultimo_pago = timezone.now()
            pago.proximo_pago = calcular_proximo_pago(pago)
            pago.plan_vencido = False
            pago.monto_cargos_unicos = Decimal("0.00")
            pago.guardar_totales()

            if not pago.titular.plan_activo:
                pago.titular.plan_activo = True
                pago.titular.save(update_fields=["plan_activo"])

        return factura, creada

from datetime import timedelta

def generar_reporte(pago_id):
    print(f"Generando reporte para el pago con ID: {pago_id}")

    with transaction.atomic():

        pago = (
            Pago.objects
            .select_for_update()
            .select_related("titular")
            .get(pk=pago_id)
        )

        fecha_hoy = timezone.now().date()

        inicio_semana = fecha_hoy - timedelta(days=fecha_hoy.weekday())

        reporte_diario, creado_d = Reporte.objects.get_or_create(
            fecha_generacion=fecha_hoy,
            defaults={
                'valor_total_recaudado': 0,
                'diario': True
            }
        )
        reporte_diario.valor_total_recaudado += pago.monto_total_a_pagar
        reporte_diario.save()

        reporte_semanal, creado_s = Reporte.objects.get_or_create(
            fecha_generacion=inicio_semana,  
            defaults={
                'valor_total_recaudado': 0,
                'semanal': True
            }
        )
        reporte_semanal.valor_total_recaudado += pago.monto_total_a_pagar
        reporte_semanal.save()

        print(f"Reporte diario {'creado' if creado_d else 'actualizado'}: {reporte_diario.valor_total_recaudado}")
        print(f"Reporte semanal {'creado' if creado_s else 'actualizado'}: {reporte_semanal.valor_total_recaudado}")

    print(pago)

