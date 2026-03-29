import ipaddress
from django.http import HttpResponseForbidden
from django.conf import settings

# Cloudflare published IP ranges — https://www.cloudflare.com/ips/
# Review and update this list periodically when Cloudflare announces new ranges.
_CLOUDFLARE_RANGES = [
    # IPv4
    '173.245.48.0/20',
    '103.21.244.0/22',
    '103.22.200.0/22',
    '103.31.4.0/22',
    '141.101.64.0/18',
    '108.162.192.0/18',
    '190.93.240.0/20',
    '188.114.96.0/20',
    '197.234.240.0/22',
    '198.41.128.0/17',
    '162.158.0.0/15',
    '104.16.0.0/13',
    '104.24.0.0/14',
    '172.64.0.0/13',
    '131.0.72.0/22',
    # IPv6
    '2400:cb00::/32',
    '2606:4700::/32',
    '2803:f800::/32',
    '2405:b500::/32',
    '2405:8100::/32',
    '2a06:98c0::/29',
    '2c0f:f248::/32',
]

# Pre-compile once at startup — avoids re-parsing on every request
_CF_NETWORKS = [ipaddress.ip_network(r) for r in _CLOUDFLARE_RANGES]


def _is_cloudflare_ip(ip_str):
    """Return True if ip_str falls within Cloudflare's published IP ranges."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in _CF_NETWORKS)
    except ValueError:
        return False


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
        if not _is_cloudflare_ip(remote_addr):
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
