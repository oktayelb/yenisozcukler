# core/models.py
"""Aktivite logu.

`core` alan modeli tutmaz; buradaki tek model altyapıya ait telemetridir:
her HTTP isteği için bir satır. Yazma işi `core.logger` içindeki arka plan
kuyruğundan toplu (bulk) yapılır, istek thread'i veritabanına dokunmaz.
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class ActivityLog(models.Model):
    # Middleware'in URL adından türettiği genel eylemler
    ACTION_PAGE_VIEW = 'page_view'
    ACTION_API = 'api'
    ACTION_ADMIN = 'admin'

    ACTION_CHOICES = [
        ('page_view', 'Sayfa görüntüleme'),
        ('api', 'API isteği'),
        ('admin', 'Admin paneli'),
        ('login', 'Giriş'),
        ('login_failed', 'Başarısız giriş'),
        ('logout', 'Çıkış'),
        ('register', 'Kayıt'),
        ('register_failed', 'Başarısız kayıt'),
        ('word_add', 'Sözcük ekleme'),
        ('comment_add', 'Yorum ekleme'),
        ('vote', 'Oylama'),
        ('example_add', 'Örnek cümle ekleme'),
        ('password_change', 'Şifre değişikliği'),
        ('username_change', 'Kullanıcı adı değişikliği'),
        ('notifications_read', 'Bildirim okundu'),
        ('admin_word_action', 'Admin sözcük işlemi'),
        ('blocked', 'Engellendi'),
    ]

    timestamp = models.DateTimeField(default=timezone.now, verbose_name='Zaman')
    action = models.CharField(max_length=24, choices=ACTION_CHOICES, default='page_view',
                              verbose_name='Eylem')

    # Kullanıcı silinse bile kayıt kalsın; username anlık kopyadır.
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
        db_index=False,
        verbose_name='Kullanıcı',
    )
    username = models.CharField(max_length=150, blank=True, default='',
                                verbose_name='Kullanıcı adı')

    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    method = models.CharField(max_length=8, default='', verbose_name='Metot')
    path = models.CharField(max_length=300, default='', verbose_name='Yol')
    query = models.CharField(max_length=200, blank=True, default='', verbose_name='Sorgu')
    status_code = models.PositiveSmallIntegerField(default=0, verbose_name='Durum kodu')
    duration_ms = models.PositiveIntegerField(default=0, verbose_name='Süre (ms)')

    detail = models.CharField(max_length=200, blank=True, default='', verbose_name='Ayrıntı')
    user_agent = models.CharField(max_length=200, blank=True, default='', verbose_name='Tarayıcı')
    is_bot = models.BooleanField(default=False, verbose_name='Bot')

    class Meta:
        verbose_name = 'Aktivite logu'
        verbose_name_plural = 'Aktivite logları'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['-timestamp'], name='actlog_ts_idx'),
            models.Index(fields=['action', '-timestamp'], name='actlog_action_ts_idx'),
            models.Index(fields=['user', '-timestamp'], name='actlog_user_ts_idx'),
            models.Index(fields=['ip', '-timestamp'], name='actlog_ip_ts_idx'),
        ]

    @property
    def display_user(self):
        if self.username:
            return self.username
        return 'Misafir'

    def __str__(self):
        return f'{self.timestamp:%d.%m.%Y %H:%M:%S} {self.action} {self.path}'
