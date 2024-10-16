from django.apps import AppConfig


class ImmigrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'immigration'

    def ready(self):
        import immigration.signals  # Import the signals to ensure they are registered