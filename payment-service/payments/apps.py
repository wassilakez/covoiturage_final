# payments/apps.py

from django.apps import AppConfig

class PaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'payments'
    
    def ready(self):
        """Importer les signaux au démarrage"""
        try:
            import payments.signals
        except ImportError:
            pass