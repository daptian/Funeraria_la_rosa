from django.contrib import admin
from .models import Factura, Pago, Plan, Reporte

# Register your models here.
admin.site.register(Pago)
admin.site.register(Factura)
admin.site.register(Plan)
admin.site.register(Reporte)
