import ipaddress
import logging
import threading
import time
import urllib.request
import uuid

from django.http import HttpResponseForbidden
from django.conf import settings
from django.utils import timezone

from . import audit

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


def _is_cloudflare_ip(ip_str):
    return _cf_cache.contains(ip_str)


class AuditLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not audit.should_log_request(request):
            return self.get_response(request)

        request_id = uuid.uuid4()
        started_perf = time.perf_counter()
        started_at = timezone.now()
        request._audit_request_id = request_id
        request_log = audit.start_request_log(request, request_id, started_at)
        request._audit_request_log = request_log
        context_tokens = audit.bind_audit_context(request, request_log)

        response = None
        caught_exception = None
        try:
            response = self.get_response(request)
            return response
        except Exception as exc:
            caught_exception = exc
            raise
        finally:
            duration_ms = audit.elapsed_ms(started_perf)
            audit.finish_request_log(
                request_log,
                request,
                response,
                duration_ms,
                exc=caught_exception,
            )
            audit.record_view_call(
                request,
                request_log,
                duration_ms,
                exc=caught_exception,
            )
            audit.reset_audit_context(context_tokens)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not getattr(request, '_audit_request_id', None):
            return None

        audit.remember_actor_at_view(request)
        view_info = audit.describe_view(request, view_func, view_args, view_kwargs)
        request._audit_view_info = view_info
        request._audit_route_name = view_info.get('route_name', '')
        request._audit_view_name = view_info.get('view_name', '')

        request_log = getattr(request, '_audit_request_log', None)
        if request_log is not None:
            request_log.route_name = request._audit_route_name
            request_log.view_name = request._audit_view_name

        return None


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

        # Production: enforce Cloudflare proxying

        # 1. CF-Connecting-IP header must be present
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if not cf_ip:
            return HttpResponseForbidden("Erişim Engellendi.")

        # 2. The actual TCP connection must originate from a real Cloudflare server.
        #    Without this check an attacker who knows the origin IP can bypass rate
        #    limits by forging a fake CF-Connecting-IP header.
        if not _cf_cache.contains(remote_addr):
            return HttpResponseForbidden("Erişim Engellendi.")

        return self._add_security_headers(self.get_response(request))

    @staticmethod
    def _add_security_headers(response):
        # Disable access to sensitive browser features not needed by this site.
        # Django's built-in middleware covers X-Frame-Options, X-Content-Type-Options,
        # and HSTS — no need to duplicate those here.
        response.setdefault(
            'Permissions-Policy',
            'geolocation=(), microphone=(), camera=(), payment=(), usb=()'
        )
        return response
