"""Aktivite logu middleware'leri.

`ActivityLogMiddleware` her isteği log kuyruğuna bırakır,
`BannedIPMiddleware` yasaklı IP'leri (admin'deki `BannedIP`) siteye sokmaz.
"""

import logging
import threading
import time
from datetime import timedelta

from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpResponseForbidden
from django.utils import timezone

from core.http import clean_ip, get_client_ip, is_public_ip, is_scanner_path

from . import ban_pass
from .logger import is_configured, log_activity, record_request, setting

logger = logging.getLogger(__name__)


class ActivityLogMiddleware:
    """Her isteği `logs.logger` kuyruğuna bırakır.

    İstek thread'inde yapılan iş: bir zaman ölçümü + bir dict + kuyruğa put.
    Veritabanı yazımı arka plandaki writer thread'inde toplu yapılır.

    MIDDLEWARE listesinde olabildiğince dışta durur; böylece Cloudflare
    engellemeleri, CSRF hataları ve 404'ler de loglanır.
    """

    def __init__(self, get_response):
        # Kill switch'e bakılır, `is_enabled()`e değil: ikincisi yazma hatası
        # molasında da False döner ve middleware bir kez kaldırılırsa mola
        # bitince geri gelmezdi.
        if not is_configured():
            raise MiddlewareNotUsed

        self.get_response = get_response
        self.exclude = tuple(setting('ACTIVITY_LOG_EXCLUDE_PREFIXES'))

    def __call__(self, request):
        if request.path.startswith(self.exclude):
            return self.get_response(request)

        start = time.perf_counter()
        response = None
        try:
            response = self.get_response(request)
            return response
        finally:
            # try/finally: `get_response` istisna fırlatsa bile satır yazılır.
            # Django istisnaları normalde 500'e çevirir, ama çeviricinin de
            # patladığı hâlde sessizce kayıt kaybetmeyelim.
            duration_ms = int((time.perf_counter() - start) * 1000)
            try:
                record_request(request, response, duration_ms)
            except Exception:
                logger.warning('activity log kaydı başarısız', exc_info=True)


# Yasaklı IP listesinin en geç kaç saniyede bir tazeleneceği. Kaydı değiştiren
# process'te sinyal sayesinde hemen, diğer gunicorn worker'larında en geç bu
# kadar sonra etkili olur.
BANNED_IPS_REFRESH_SECONDS = 30.0


class _BannedIPCache:
    """Yasaklı IP'lerin process'teki kopyası; istek başına sorgu atılmasın diye."""

    def __init__(self):
        self._ips = frozenset()
        self._loaded_at = None
        self._lock = threading.Lock()

    def invalidate(self):
        self._loaded_at = None

    def contains(self, ip):
        if ip is None:
            return False
        if not self._is_fresh():
            with self._lock:
                # Kilidi beklerken başka bir thread tazelemiş olabilir.
                if not self._is_fresh():
                    self._refresh()
        return ip in self._ips

    def _is_fresh(self):
        loaded_at = self._loaded_at
        return loaded_at is not None and \
            time.monotonic() - loaded_at < BANNED_IPS_REFRESH_SECONDS

    def _refresh(self):
        from .models import BannedIP

        try:
            # `get_client_ip` ile aynı biçime getir; yoksa ör. IPv4-mapped
            # IPv6 adresleri iki tarafta farklı yazılıp eşleşmezdi.
            self._ips = frozenset(filter(None, (
                clean_ip(ip) for ip in BannedIP.active().values_list('ip', flat=True)
            )))
        except Exception as exc:
            # Ör. migration henüz uygulanmadı: site kapanmasın, eldekiyle devam.
            logger.warning('yasaklı IP listesi okunamadı, eldeki kullanılıyor: %s', exc)
        self._loaded_at = time.monotonic()


_banned_ips = _BannedIPCache()


def invalidate_banned_ips():
    """Yasaklı IP listesi değişti: bu process bir sonraki istekte yeniden okusun."""
    _banned_ips.invalidate()


class BannedIPMiddleware:
    """Yasaklı IP'lerden gelen her isteğe 403 döner.

    `ActivityLogMiddleware`'den içeride durur; engellenen istekler aktivite
    logunda 'blocked' olarak görünür.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)
        if not _banned_ips.contains(ip):
            return self.get_response(request)
        if request.path == ban_pass.PATH:
            return self.get_response(request)
        if ban_pass.has_pass(request, ip):
            log_activity(request, detail='Yasaklı IP, doğrulanmış tarayıcı')
            return self.get_response(request)
        log_activity(request, 'blocked', detail='Yasaklı IP')
        return ban_pass.blocked_response(request)


SCANNER_BAN_DAYS = 7


class ScannerTrapMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not is_scanner_path(request.path):
            return self.get_response(request)
        user = getattr(request, 'user', None)
        if user is not None and user.is_staff:
            return self.get_response(request)

        ip = get_client_ip(request)
        if is_public_ip(ip):
            ban_ip_for_scanning(ip)
            detail = f'Tarama yolu, IP {SCANNER_BAN_DAYS} gün yasaklandı'
        else:
            detail = 'Tarama yolu'
        log_activity(request, 'blocked', detail=detail)
        return HttpResponseForbidden('Erişim Engellendi.')


def ban_ip_for_scanning(ip):
    from .models import BannedIP

    now = timezone.now()
    expires_at = now + timedelta(days=SCANNER_BAN_DAYS)
    try:
        ban, created = BannedIP.objects.get_or_create(
            ip=ip,
            defaults={'reason': 'Tarama yolu isteği (otomatik)', 'expires_at': expires_at},
        )
        if not created and ban.expires_at is not None and ban.expires_at <= now:
            ban.expires_at = expires_at
            ban.save(update_fields=['expires_at'])
    except Exception:
        logger.warning('tarayıcı IP yasaklanamadı: %s', ip, exc_info=True)
