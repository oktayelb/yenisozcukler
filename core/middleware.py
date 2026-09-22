"""Cloudflare önünde çalışmayı zorunlu kılan güvenlik katmanı.

Aktivite logu middleware'i `logs.middleware` içinde.
"""

import ipaddress
import logging
import threading
import time
import urllib.request
from django.http import HttpResponseForbidden
from django.conf import settings

from logs.logger import log_activity

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


def _split_by_version(ranges):
    """Ağları IPv4/IPv6 diye ayırır: `contains` yalnızca ilgili yarıyı tarar."""
    by_version = {4: [], 6: []}
    for item in ranges:
        try:
            net = ipaddress.ip_network(item)
        except ValueError:
            logger.warning('Cloudflare aralığı ayrıştırılamadı, atlandı: %r', item)
            continue
        by_version[net.version].append(net)
    return by_version


class _CfIpCache:
    """Holds Cloudflare IP networks, refreshed daily in a background thread."""

    def __init__(self):
        self._by_version = _split_by_version(_FALLBACK_RANGES)
        self._lock = threading.Lock()
        # None = hiç denenmedi. 0.0 olsaydı `monotonic()` makine açılışından
        # sayıldığı için ilk yenileme ancak 24 saatlik uptime'dan sonra olurdu.
        self._last_attempt = None
        self._refresh_in_progress = False

    def contains(self, ip_str):
        self._maybe_refresh()
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        with self._lock:
            networks = self._by_version[ip.version]
        # Liste atomik olarak değiştirildiği için tarama kilit dışında:
        # her istekte tutulan kilit gereksiz bir darboğaz olurdu.
        return any(ip in net for net in networks)

    def _maybe_refresh(self):
        last = self._last_attempt
        if last is not None and time.monotonic() - last < _CF_REFRESH_SECONDS:
            return
        if self._refresh_in_progress:
            return
        self._refresh_in_progress = True
        # Deneme anını hemen işaretle: aksi hâlde Cloudflare'a ulaşılamadığında
        # her istek yeni bir thread açar (başarısızlıkta thread yağmuru).
        self._last_attempt = time.monotonic()
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
            by_version = _split_by_version(ranges)
            if not by_version[4]:
                # Boş/bozuk yanıt tüm siteyi kilitler; eldekini koru.
                raise ValueError('Cloudflare listesi boş döndü')
            with self._lock:
                self._by_version = by_version
            logger.debug(
                'Cloudflare IP list refreshed (%d v4, %d v6)',
                len(by_version[4]), len(by_version[6]),
            )
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
