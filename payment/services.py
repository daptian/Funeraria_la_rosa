from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import Factura, Pago, Reporte
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.http import JsonResponse
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from datetime import datetime
from django.http import HttpResponse
from io import BytesIO


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


def obtener_siguiente_periodo_pago(pago):
    fecha_base = pago.proximo_pago or pago.titular.fecha_ingreso or timezone.localdate()
    return (fecha_base.year, fecha_base.month)


def obtener_datos_reporte_pdf():
    datos = {
        'diario': [],
        'semanal': [],
        'mensual': [],
    }

    reportes = Reporte.objects.order_by('fecha_generacion')
    for reporte in reportes:
        if reporte.diario:
            datos['diario'].append({
                'fecha': reporte.fecha_generacion,
                'monto': reporte.valor_total_recaudado,
            })
        if reporte.semanal:
            datos['semanal'].append({
                'fecha': reporte.fecha_generacion,
                'monto': reporte.valor_total_recaudado,
            })
        if reporte.mensual:
            datos['mensual'].append({
                'fecha': reporte.fecha_generacion,
                'monto': reporte.valor_total_recaudado,
            })

    return datos


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
        fin_semana = inicio_semana + timedelta(days=6)
        inicio_mes = fecha_hoy.replace(day=1)

        Reporte.objects.filter(diario=True, fecha_generacion__lt=fecha_hoy).update(diario=False)

        reporte_diario, creado_d = Reporte.objects.get_or_create(
            fecha_generacion=fecha_hoy,
            defaults={
                'valor_total_recaudado': 0,
                'diario': True
            }
        )

        reporte_diario.valor_total_recaudado += pago.monto_total_a_pagar
        reporte_diario.diario = True
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

        reporte_mensual, creado_m = Reporte.objects.get_or_create(
            fecha_generacion=inicio_mes,
            defaults={
                'valor_total_recaudado': 0,
                'mensual': True
            }
        )
        reporte_mensual.valor_total_recaudado += pago.monto_total_a_pagar
        reporte_mensual.save()

        return {
            'reporte_diario': {
                'fecha_generacion': str(reporte_diario.fecha_generacion),
                'valor_total_recaudado': str(reporte_diario.valor_total_recaudado),
            },
            'reporte_semanal': {
                'fecha_generacion': str(reporte_semanal.fecha_generacion),
                'fecha_inicio': str(inicio_semana),
                'fecha_fin': str(fin_semana),
                'valor_total_recaudado': str(reporte_semanal.valor_total_recaudado),
            },
            'reporte_mensual': {
                'fecha_generacion': str(reporte_mensual.fecha_generacion),
                'valor_total_recaudado': str(reporte_mensual.valor_total_recaudado),
            },
        }

        print(f"Reporte diario {'creado' if creado_d else 'actualizado'}: {reporte_diario.valor_total_recaudado}")
        print(f"Reporte semanal {'creado' if creado_s else 'actualizado'}: {reporte_semanal.valor_total_recaudado}")
        print(f"Reporte mensual {'creado' if creado_m else 'actualizado'}: {reporte_mensual.valor_total_recaudado}")

    print(pago)


def _formatear_moneda(valor):
    return f"${Decimal(str(valor)).quantize(Decimal('0.01')):,.2f}"


def _crear_tabla_reporte(titulo, filas):
    headers = ["Fecha", "Total recaudado"]
    data = [headers] + filas
    tabla = Table(data, colWidths=[2.8 * inch, 2.6 * inch])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2F4F4F')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.beige]),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    return Paragraph(f"<b>{titulo}</b>", getSampleStyleSheet()['Heading2']), tabla


def generar_pdf_reporte_completo(request):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=35,
        rightMargin=35,
        topMargin=35,
        bottomMargin=35,
    )
    elements = []

    datos = obtener_datos_reporte_pdf()

    titulo = Paragraph("<b>Reporte de Ingresos Completo</b>", getSampleStyleSheet()['Title'])
    elements.append(titulo)
    elements.append(Spacer(1, 0.2 * inch))

    fecha_generacion = Paragraph(
        f"<b>Generado:</b> {datetime.now().strftime('%a, %d %b %Y %H:%M')}",
        getSampleStyleSheet()['Normal'],
    )
    elements.append(fecha_generacion)
    elements.append(Spacer(1, 0.35 * inch))

    tipos = [
        ('diario', 'Reporte Diario'),
        ('semanal', 'Reporte Semanal'),
        ('mensual', 'Reporte Mensual'),
    ]

    for clave, nombre in tipos:
        filas = []
        for item in datos.get(clave, []):
            filas.append([
                item['fecha'].strftime('%d/%m/%Y'),
                _formatear_moneda(item['monto']),
            ])

        if not filas:
            filas = [["Sin registros", "$0.00"]]

        titulo_tabla, tabla = _crear_tabla_reporte(nombre, filas)
        elements.append(titulo_tabla)
        elements.append(Spacer(1, 0.15 * inch))
        elements.append(tabla)
        elements.append(Spacer(1, 0.25 * inch))

    doc.build(elements)

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_ingresos.pdf"'
    return response