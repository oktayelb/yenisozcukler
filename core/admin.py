# core/admin.py
"""Aktivite logu admin'i.

`core`'un tek modeli ActivityLog olduğu için burada başka bir şey yok;
sözcük/yorum admin'leri `words.admin`, kullanıcı admin'i `accounts.admin`.
"""

from datetime import timedelta

from django.contrib import admin
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from .models import ActivityLog

ACTION_COLORS = {
    'login': '#2e7d32',
    'register': '#1565c0',
    'logout': '#757575',
    'login_failed': '#c62828',
    'register_failed': '#c62828',
    'blocked': '#b71c1c',
    'word_add': '#6a1b9a',
    'comment_add': '#00838f',
    'vote': '#ef6c00',
    'example_add': '#00695c',
    'password_change': '#ad1457',
    'username_change': '#ad1457',
    'admin_word_action': '#4527a0',
    'admin': '#37474f',
    'api': '#90a4ae',
    'page_view': '#b0bec5',
}


class StatusGroupFilter(admin.SimpleListFilter):
    """HTTP durum kodunu 2xx/3xx/4xx/5xx olarak grupla."""
    title = 'HTTP durumu'
    parameter_name = 'status_group'

    def lookups(self, request, model_admin):
        return [
            ('2xx', 'Başarılı (2xx)'),
            ('3xx', 'Yönlendirme (3xx)'),
            ('4xx', 'İstemci hatası (4xx)'),
            ('429', 'Rate limit (429)'),
            ('5xx', 'Sunucu hatası (5xx)'),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value == '429':
            return queryset.filter(status_code=429)
        if value in ('2xx', '3xx', '4xx', '5xx'):
            low = int(value[0]) * 100
            return queryset.filter(status_code__gte=low, status_code__lt=low + 100)
        return queryset


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        'when', 'action_label', 'who', 'ip', 'method',
        'target', 'status_label', 'took', 'detail',
    )
    list_filter = ('action', StatusGroupFilter, 'is_bot', 'method', 'timestamp')
    search_fields = ('path', 'username', 'ip', 'detail', 'user_agent')
    search_help_text = 'Yol, kullanıcı adı, IP veya ayrıntı içinde ara.'
    date_hierarchy = 'timestamp'
    list_select_related = ('user',)
    list_per_page = 50
    # Milyonlarca satırda COUNT(*) pahalı; toplam sayıyı hesaplama.
    show_full_result_count = False
    ordering = ('-id',)
    actions = ['prune_old_logs']

    @admin.display(description='Zaman', ordering='-id')
    def when(self, obj):
        return timezone.localtime(obj.timestamp).strftime('%d.%m.%Y %H:%M:%S')

    @admin.display(description='Eylem', ordering='action')
    def action_label(self, obj):
        color = ACTION_COLORS.get(obj.action, '#546e7a')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px;white-space:nowrap;">{}</span>',
            color, obj.get_action_display(),
        )

    @admin.display(description='Kullanıcı', ordering='username')
    def who(self, obj):
        if obj.username:
            return format_html('<b>{}</b>', obj.username)
        label = 'bot' if obj.is_bot else 'misafir'
        return format_html('<span style="color:#888;">{}</span>', label)

    @admin.display(description='Yol', ordering='path')
    def target(self, obj):
        if obj.query:
            return format_html(
                '{}<span style="color:#999;">?{}</span>', obj.path, obj.query[:60]
            )
        return obj.path

    @admin.display(description='Durum', ordering='status_code')
    def status_label(self, obj):
        code = obj.status_code
        if code >= 500:
            color = '#c62828'
        elif code == 429:
            color = '#ef6c00'
        elif code >= 400:
            color = '#e65100'
        elif code >= 300:
            color = '#616161'
        else:
            color = '#2e7d32'
        return format_html('<b style="color:{};">{}</b>', color, code)

    @admin.display(description='Süre', ordering='duration_ms')
    def took(self, obj):
        color = '#c62828' if obj.duration_ms >= 1000 else '#555'
        return format_html('<span style="color:{};">{} ms</span>', color, obj.duration_ms)

    # Loglar salt okunurdur: elle eklenip düzenlenemez, sadece silinebilir.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    @admin.action(description='Saklama süresini aşan tüm logları sil')
    def prune_old_logs(self, request, queryset):
        from .logger import setting
        days = setting('ACTIVITY_LOG_RETENTION_DAYS') or 30
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = ActivityLog.objects.filter(timestamp__lt=cutoff).delete()
        self.message_user(request, f'{days} günden eski {deleted} log silindi.')

    def changelist_view(self, request, extra_context=None):
        since = timezone.now() - timedelta(hours=24)
        stats = ActivityLog.objects.filter(timestamp__gte=since).aggregate(
            total=Count('id'),
            humans=Count('id', filter=Q(is_bot=False)),
            visitors=Count('ip', filter=Q(is_bot=False), distinct=True),
            logins=Count('id', filter=Q(action='login')),
            failed_logins=Count('id', filter=Q(action__in=['login_failed', 'blocked'])),
            registrations=Count('id', filter=Q(action='register')),
            words=Count('id', filter=Q(action='word_add', status_code__lt=400)),
            comments=Count('id', filter=Q(action='comment_add', status_code__lt=400)),
            votes=Count('id', filter=Q(action='vote', status_code__lt=400)),
            errors=Count('id', filter=Q(status_code__gte=500)),
        )
        extra_context = extra_context or {}
        extra_context['activity_stats'] = [
            ('İstek', stats['total']),
            ('Bot dışı istek', stats['humans']),
            ('Tekil ziyaretçi', stats['visitors']),
            ('Giriş', stats['logins']),
            ('Başarısız giriş', stats['failed_logins']),
            ('Yeni kayıt', stats['registrations']),
            ('Yeni sözcük', stats['words']),
            ('Yorum', stats['comments']),
            ('Oy', stats['votes']),
            ('Sunucu hatası', stats['errors']),
        ]
        return super().changelist_view(request, extra_context)
