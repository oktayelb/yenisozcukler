"""Aktivite logu middleware'leri.

`ActivityLogMiddleware` her isteği log kuyruğuna bırakır,
`BannedIPMiddleware` yasaklı IP'leri (admin'deki `BannedIP`) siteye sokmaz.
"""

import logging
import threading
import time

from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpResponseForbidden

from core.http import clean_ip, get_client_ip

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
                clean_ip(ip) for ip in BannedIP.objects.values_list('ip', flat=True)
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
        if _banned_ips.contains(get_client_ip(request)):
            log_activity(request, 'blocked', detail='Yasaklı IP')
            return HttpResponseForbidden('Erişim Engellendi.')
        return self.get_response(request)
