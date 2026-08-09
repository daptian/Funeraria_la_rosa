from django.urls import path
from . import views

urlpatterns = [
    path('pagos/', views.payments_dashboard, name='payments'),
    path('reportes/', views.report_dashboard, name='report'),
    path('pagos/<int:pago_id>/factura/', views.generar_factura, name='generate_invoice'),
    path('facturas/<int:factura_id>/', views.invoice_detail, name='invoice_detail'),
        # APIs para los gráficos
    path('api/reportes-diarios/', views.api_reportes_diarios, name='api_reportes_diarios'),
    path('api/reportes-semanales/', views.api_reportes_semanales, name='api_reportes_semanales'),
    path('api/reportes-mensuales/', views.api_reportes_mensuales, name='api_reportes_mensuales'),
    path('api/afiliaciones/', views.api_afiliaciones, name='api_afiliaciones'),
]

