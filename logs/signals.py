# logs/signals.py

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .middleware import invalidate_banned_ips
from .models import BannedIP


# Admin'de eklenen/silinen yasak bu process'te hemen etkili olsun; diğer
# worker'lar listeyi zaten kısa aralıklarla tazeliyor.
@receiver(post_save, sender=BannedIP)
@receiver(post_delete, sender=BannedIP)
def refresh_banned_ips(sender, **kwargs):
    invalidate_banned_ips()
