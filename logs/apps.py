from django.apps import AppConfig


class LogsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'logs'
    verbose_name = 'Aktivite logu'

    def ready(self):
        # Sinyalleri import ediyoruz ki Django başlarken kaydetsin
        import logs.signals  # noqa: F401
