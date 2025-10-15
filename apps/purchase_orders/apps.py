from django.apps import AppConfig

class PurchaseOrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.purchase_orders'

    def ready(self):
        # Import signals to ensure they're connected
        try:
            import apps.purchase_orders.signals
        except ImportError:
            pass