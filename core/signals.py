# core/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Word, Comment

@receiver(post_save, sender=User)
def claim_guest_content(sender, instance, created, **kwargs):
    if created:
        nickname = instance.username
        
        # DÜZELTME: 'author' yerine 'author__iexact' kullanıyoruz.
        # Böylece "oktay" takma adını "Oktay" kullanıcısına da bağlar.
        
        Word.objects.filter(
            author__iexact=nickname, 
            user__isnull=True
        ).update(user=instance)
        
        Comment.objects.filter(
            author__iexact=nickname, 
            user__isnull=True
        ).update(user=instance)