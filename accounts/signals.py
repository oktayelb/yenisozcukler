# accounts/signals.py

from django.db.models.signals import post_save, pre_delete
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.contrib.auth.models import User

from core.logger import log_activity
from words.models import Word, Comment


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

        from challenge.models import TranslationChallenge, ChallengeComment

        TranslationChallenge.objects.filter(
            author__iexact=nickname,
            user__isnull=True
        ).update(user=instance)

        ChallengeComment.objects.filter(
            author__iexact=nickname,
            user__isnull=True
        ).update(user=instance)


@receiver(pre_delete, sender=User)
def anonymize_deleted_user_content(sender, instance, **kwargs):
    anonymous_label = 'silinmiş kullanıcı'

    Word.objects.filter(user=instance).update(author=anonymous_label)
    Comment.objects.filter(user=instance).update(author=anonymous_label)

    from challenge.models import TranslationChallenge, ChallengeComment

    TranslationChallenge.objects.filter(user=instance).update(author=anonymous_label)
    ChallengeComment.objects.filter(user=instance).update(author=anonymous_label)


# --- AKTİVİTE LOGU SİNYALLERİ ---
# Bunlar sayesinde admin panelinden yapılan giriş/çıkışlar da API'dekilerle
# aynı log satırlarına düşer. Sadece request üzerine etiket koyarlar;
# satırı ActivityLogMiddleware yazar.

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    log_activity(request, 'login', username=user.get_username(), user=user)


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    # `user`'ı açıkça geçiyoruz: bu sinyalden hemen sonra `logout()`
    # request.user'ı AnonymousUser yapıyor ve satır sahipsiz kalıyordu.
    if user is not None:
        log_activity(request, 'logout', username=user.get_username(), user=user)


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials=None, request=None, **kwargs):
    # authenticate() şifre değişikliği gibi başka akışlarda da çağrılır;
    # o view'lar eylemi önceden işaretlediği için set_default=True kullanıyoruz.
    if request is None:
        return
    username = (credentials or {}).get('username') or ''
    log_activity(request, 'login_failed', username=username, set_default=True)
