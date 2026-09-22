import ipaddress
import logging
import threading
import time
import urllib.request
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpResponseForbidden
from django.conf import settings

from .logger import is_configured, log_activity, record_request, setting

logger = logging.getLogger(__name__)

_CF_IPV4_URL = 'https://www.cloudflare.com/ips-v4'
_CF_IPV6_URL = 'https://www.cloudflare.com/ips-v6'
_CF_REFRESH_SECONDS = 86400  # refresh daily

# Last-known-good fallback used when the live fetch fails
_FALLBACK_RANGES = [
    # IPv4
    '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22',
    '103.31.4.0/22', '141.101.64.0/18', '108.162.192.0/18',
    '190.93.240.0/20', '188.114.96.0/20', '197.234.240.0/22',
    '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13',
    '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22',
    # IPv6
    '2400:cb00::/32', '2606:4700::/32', '2803:f800::/32',
    '2405:b500::/32', '2405:8100::/32', '2a06:98c0::/29',
    '2c0f:f248::/32',
]


class _CfIpCache:
    """Holds Cloudflare IP networks, refreshed daily in a background thread."""

    def __init__(self):
        self._networks = [ipaddress.ip_network(r) for r in _FALLBACK_RANGES]
        self._lock = threading.Lock()
        self._last_refreshed = 0.0
        self._refresh_in_progress = False

    def contains(self, ip_str):
        self._maybe_refresh()
        try:
            ip = ipaddress.ip_address(ip_str)
            with self._lock:
                return any(ip in net for net in self._networks)
        except ValueError:
            return False

    def _maybe_refresh(self):
        if time.monotonic() - self._last_refreshed < _CF_REFRESH_SECONDS:
            return
        if self._refresh_in_progress:
            return
        self._refresh_in_progress = True
        t = threading.Thread(target=self._do_refresh, daemon=True)
        t.start()

    def _do_refresh(self):
        try:
            ranges = []
            for url in (_CF_IPV4_URL, _CF_IPV6_URL):
                with urllib.request.urlopen(url, timeout=5) as resp:
                    body = resp.read().decode('utf-8')
                    ranges.extend(
                        line.strip() for line in body.splitlines() if line.strip()
                    )
            networks = [ipaddress.ip_network(r) for r in ranges]
            with self._lock:
                self._networks = networks
                self._last_refreshed = time.monotonic()
            logger.debug('Cloudflare IP list refreshed (%d networks)', len(networks))
        except Exception as exc:
            logger.warning('Could not refresh Cloudflare IP list, keeping previous: %s', exc)
        finally:
            self._refresh_in_progress = False


_cf_cache = _CfIpCache()


class CloudflareSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        remote_addr = request.META.get('REMOTE_ADDR', '')

        # Always allow localhost (development)
        if remote_addr in ('127.0.0.1', '::1'):
            return self._add_security_headers(self.get_response(request))

        # Allow all in DEBUG mode
        if settings.DEBUG:
            return self._add_security_headers(self.get_response(request))

        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if not cf_ip:
            return self._blocked(request)

        if not _cf_cache.contains(remote_addr):
            return self._blocked(request)

        return self._add_security_headers(self.get_response(request))

    @staticmethod
    def _blocked(request):
        # Aktivite logunda 'blocked' olarak görünsün.
        log_activity(request, 'blocked', detail='Cloudflare dışı istek')
        return HttpResponseForbidden("Erişim Engellendi.")

    @staticmethod
    def _add_security_headers(response):
        response.setdefault(
            'Permissions-Policy',
            'geolocation=(), microphone=(), camera=(), payment=(), usb=()'
        )
        return response


class ActivityLogMiddleware:
    """Her isteği `core.logger` kuyruğuna bırakır.

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
