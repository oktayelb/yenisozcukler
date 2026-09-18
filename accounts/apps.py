from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # Sinyalleri import ediyoruz ki Django başlarken kaydetsin
        import accounts.signals  # noqa: F401
