# apps/reportes/apps.py

from django.apps import AppConfig

class ReportesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'historial'  # O el nombre de tu app
    
    def ready(self):
        import historial.signals  # Importa los signals al iniciar