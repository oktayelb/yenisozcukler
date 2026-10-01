# logs/admin.py
"""Aktivite logu admin'i.

Sözcük/yorum admin'leri `words.admin`, kullanıcı admin'i `accounts.admin`.
"""

from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from core.http import clean_ip, get_client_ip

from .logger import prune_logs
from .middleware import invalidate_banned_ips
from .models import ActivityLog, BannedIP

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


class PruneLogsForm(forms.Form):
    days = forms.IntegerField(
        label='Kaç günden eski', min_value=0, initial=30,
        help_text='Bu günden eski loglar silinir. 0 yazarsanız tüm loglar silinir.',
    )


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
    actions = ['ban_selected_ips']
    # Temizleme isteği gunicorn'un 30 saniyelik timeout'una takılmasın.
    PRUNE_MAX_SECONDS = 20

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

    def has_ban_permission(self, request):
        return request.user.has_perm('logs.add_bannedip')

    @admin.action(description="Seçili kayıtların IP'lerini siteden yasakla",
                  permissions=['ban'])
    def ban_selected_ips(self, request, queryset):
        ips = set(queryset.exclude(ip__isnull=True).values_list('ip', flat=True))
        own_ip = get_client_ip(request)
        if own_ip in ips:
            # Kendini yasaklayan admin panele de giremezdi.
            ips.discard(own_ip)
            self.message_user(
                request, f'Kendi IP adresiniz ({own_ip}) yasaklanmadı.', messages.WARNING,
            )
        if not ips:
            self.message_user(request, 'Yasaklanacak IP yok.', messages.WARNING)
            return
        existing = set(BannedIP.objects.filter(ip__in=ips).values_list('ip', flat=True))
        new_ips = ips - existing
        BannedIP.objects.bulk_create(
            [BannedIP(ip=ip, reason='Aktivite logundan yasaklandı') for ip in new_ips],
            ignore_conflicts=True,
        )
        # bulk_create post_save göndermez; listeyi elle tazele.
        invalidate_banned_ips()
        message = f'{len(new_ips)} IP siteden yasaklandı.'
        if existing:
            message += f' {len(existing)} IP zaten yasaklıydı.'
        self.message_user(request, message)

    def get_urls(self):
        # Varsayılan URL'lerdeki `<path:object_id>/` her şeyi yakalar; önce gelmeli.
        return [
            path('prune/', self.admin_site.admin_view(self.prune_view),
                 name='logs_activitylog_prune'),
        ] + super().get_urls()

    def prune_view(self, request):
        """Logları temizle: gün sayısı seç, kaç kaydın gideceğini gör, onayla.

        Önizleme GET, silme POST: adres çubuğundan ya da önbellekten açılan
        bir sayfa yanlışlıkla silme yapamaz.
        """
        if not self.has_delete_permission(request):
            raise PermissionDenied

        if request.method == 'POST':
            form = PruneLogsForm(request.POST)
            if form.is_valid():
                days = form.cleaned_data['days']
                # Silme parça parça yapılır — tek bir dev DELETE SQLite'ın
                # yazma kilidini dakikalarca tutabilirdi.
                deleted, finished = prune_logs(days, max_seconds=self.PRUNE_MAX_SECONDS)
                if finished:
                    self.message_user(request, f'{days} günden eski {deleted} log silindi.')
                else:
                    self.message_user(
                        request,
                        f'{deleted} log silindi ama süre sınırına ulaşıldı; '
                        f'kalanlar için işlemi tekrarlayın.',
                        messages.WARNING,
                    )
                return redirect('admin:logs_activitylog_changelist')
        else:
            form = PruneLogsForm(request.GET or None)

        preview = None
        if request.method == 'GET' and form.is_bound and form.is_valid():
            days = form.cleaned_data['days']
            cutoff = timezone.now() - timedelta(days=days)
            preview = {
                'days': days,
                'cutoff': cutoff,
                'count': ActivityLog.objects.filter(timestamp__lt=cutoff).count(),
            }

        context = {
            **self.admin_site.each_context(request),
            'title': 'Logları temizle',
            'opts': self.model._meta,
            'form': form,
            'preview': preview,
            'oldest': ActivityLog.objects.order_by('timestamp')
                      .values_list('timestamp', flat=True).first(),
        }
        return TemplateResponse(request, 'admin/logs/activitylog/prune.html', context)

    def changelist_view(self, request, extra_context=None):
        since = timezone.now() - timedelta(hours=24)
        stats = ActivityLog.objects.filter(timestamp__gte=since).aggregate(
            total=Count('id'),
            humans=Count('id', filter=Q(is_bot=False)),
            visitors=Count('ip', filter=Q(is_bot=False), distinct=True),
            logins=Count('id', filter=Q(action='login')),
            failed_logins=Count('id', filter=Q(action='login_failed')),
            blocked=Count('id', filter=Q(action='blocked')),
            registrations=Count('id', filter=Q(action='register')),
            words=Count('id', filter=Q(action='word_add', status_code__lt=400)),
            comments=Count('id', filter=Q(action='comment_add', status_code__lt=400)),
            votes=Count('id', filter=Q(action='vote', status_code__lt=400)),
            errors=Count('id', filter=Q(status_code__gte=500)),
        )
        extra_context = extra_context or {}
        extra_context['can_prune'] = self.has_delete_permission(request)
        extra_context['can_view_banned_ips'] = request.user.has_perm('logs.view_bannedip')
        extra_context['activity_stats'] = [
            ('İstek', stats['total']),
            ('Bot dışı istek', stats['humans']),
            ('Tekil ziyaretçi', stats['visitors']),
            ('Giriş', stats['logins']),
            ('Başarısız giriş', stats['failed_logins']),
            ('Engellenen istek', stats['blocked']),
            ('Yeni kayıt', stats['registrations']),
            ('Yeni sözcük', stats['words']),
            ('Yorum', stats['comments']),
            ('Oy', stats['votes']),
            ('Sunucu hatası', stats['errors']),
        ]
        return super().changelist_view(request, extra_context)


class BannedIPForm(forms.ModelForm):
    # `BannedIPAdmin.get_form` isteği yapanın IP'sini buraya koyar.
    own_ip = None

    def clean_ip(self):
        ip = self.cleaned_data['ip']
        if self.own_ip and clean_ip(ip) == self.own_ip:
            raise forms.ValidationError(
                'Bu sizin şu anki IP adresiniz; yasaklarsanız admin paneline de giremezsiniz.'
            )
        return ip


@admin.register(BannedIP)
class BannedIPAdmin(admin.ModelAdmin):
    form = BannedIPForm
    list_display = ('ip', 'reason', 'banned_at')
    search_fields = ('ip', 'reason')
    ordering = ('-created_at',)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.own_ip = get_client_ip(request)
        return form

    @admin.display(description='Yasaklanma zamanı', ordering='created_at')
    def banned_at(self, obj):
        return timezone.localtime(obj.created_at).strftime('%d.%m.%Y %H:%M')
