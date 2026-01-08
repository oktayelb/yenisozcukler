from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core' # Projenizin app adı neyse o olmalı

    def ready(self):
        # Sinyalleri import ediyoruz ki Django başlarken kaydetsin
        import core.signals