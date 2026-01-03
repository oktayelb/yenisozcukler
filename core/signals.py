# core/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Word, Comment

@receiver(post_save, sender=User)
def claim_guest_content(sender, instance, created, **kwargs):
    """
    Yeni bir kullanıcı oluşturulduğunda çalışır.
    Kullanıcının username'i ile eşleşen ve henüz bir sahibi olmayan (anonim)
    Word ve Comment'leri bulur ve bu kullanıcıya zimmetler.
    """
    if created:
        # Kullanıcının kullanıcı adını (nickname olarak kullanılan) alalım
        nickname = instance.username
        
        # 1. Sözcükleri Sahiplendir
        # Yazar adı eşleşen VE henüz bir user atanmamış (user__isnull=True) kayıtları güncelle
        updated_words = Word.objects.filter(
            author=nickname, 
            user__isnull=True
        ).update(user=instance)
        
        # 2. Yorumları Sahiplendir
        updated_comments = Comment.objects.filter(
            author=nickname, 
            user__isnull=True
        ).update(user=instance)
        
        # Loglama (İsteğe bağlı, terminalde görmek için)
        if updated_words > 0 or updated_comments > 0:
            print(f"User '{nickname}' created. Claimed {updated_words} words and {updated_comments} comments.")# core/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Word, Comment

@receiver(post_save, sender=User)
def claim_guest_content(sender, instance, created, **kwargs):
    """
    Yeni bir kullanıcı oluşturulduğunda çalışır.
    Kullanıcının username'i ile eşleşen ve henüz bir sahibi olmayan (anonim)
    Word ve Comment'leri bulur ve bu kullanıcıya zimmetler.
    """
    if created:
        # Kullanıcının kullanıcı adını (nickname olarak kullanılan) alalım
        nickname = instance.username
        
        # 1. Sözcükleri Sahiplendir
        # Yazar adı eşleşen VE henüz bir user atanmamış (user__isnull=True) kayıtları güncelle
        updated_words = Word.objects.filter(
            author=nickname, 
            user__isnull=True
        ).update(user=instance)
        
        # 2. Yorumları Sahiplendir
        updated_comments = Comment.objects.filter(
            author=nickname, 
            user__isnull=True
        ).update(user=instance)
        
        # Loglama (İsteğe bağlı, terminalde görmek için)
        if updated_words > 0 or updated_comments > 0:
            print(f"User '{nickname}' created. Claimed {updated_words} words and {updated_comments} comments.")