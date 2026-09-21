import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_remove_notification_core_notifi_recipie_b7a566_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Zaman')),
                ('action', models.CharField(choices=[('page_view', 'Sayfa görüntüleme'), ('api', 'API isteği'), ('admin', 'Admin paneli'), ('login', 'Giriş'), ('login_failed', 'Başarısız giriş'), ('logout', 'Çıkış'), ('register', 'Kayıt'), ('register_failed', 'Başarısız kayıt'), ('word_add', 'Sözcük ekleme'), ('comment_add', 'Yorum ekleme'), ('vote', 'Oylama'), ('example_add', 'Örnek cümle ekleme'), ('password_change', 'Şifre değişikliği'), ('username_change', 'Kullanıcı adı değişikliği'), ('notifications_read', 'Bildirim okundu'), ('admin_word_action', 'Admin sözcük işlemi'), ('blocked', 'Engellendi')], default='page_view', max_length=24, verbose_name='Eylem')),
                ('username', models.CharField(blank=True, default='', max_length=150, verbose_name='Kullanıcı adı')),
                ('ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP')),
                ('method', models.CharField(default='', max_length=8, verbose_name='Metot')),
                ('path', models.CharField(default='', max_length=300, verbose_name='Yol')),
                ('query', models.CharField(blank=True, default='', max_length=200, verbose_name='Sorgu')),
                ('status_code', models.PositiveSmallIntegerField(default=0, verbose_name='Durum kodu')),
                ('duration_ms', models.PositiveIntegerField(default=0, verbose_name='Süre (ms)')),
                ('detail', models.CharField(blank=True, default='', max_length=200, verbose_name='Ayrıntı')),
                ('user_agent', models.CharField(blank=True, default='', max_length=200, verbose_name='Tarayıcı')),
                ('is_bot', models.BooleanField(default=False, verbose_name='Bot')),
                ('user', models.ForeignKey(blank=True, db_index=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_logs', to=settings.AUTH_USER_MODEL, verbose_name='Kullanıcı')),
            ],
            options={
                'verbose_name': 'Aktivite logu',
                'verbose_name_plural': 'Aktivite logları',
                'ordering': ['-id'],
                'indexes': [models.Index(fields=['-timestamp'], name='actlog_ts_idx'), models.Index(fields=['action', '-timestamp'], name='actlog_action_ts_idx'), models.Index(fields=['user', '-timestamp'], name='actlog_user_ts_idx'), models.Index(fields=['ip', '-timestamp'], name='actlog_ip_ts_idx')],
            },
        ),
    ]
