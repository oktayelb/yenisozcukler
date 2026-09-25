"""CloudflareSecurityMiddleware ve Cloudflare IP listesi."""

from django.test import RequestFactory, TestCase, override_settings

from core.middleware import CloudflareSecurityMiddleware, _cf_cache


class CloudflareIPTests(TestCase):

    def test_known_cloudflare_ipv4_accepted(self):
        # 104.16.0.1 is inside 104.16.0.0/13
        self.assertTrue(_cf_cache.contains('104.16.0.1'))

    def test_known_cloudflare_ipv4_another_range(self):
        # 173.245.48.1 is inside 173.245.48.0/20
        self.assertTrue(_cf_cache.contains('173.245.48.1'))

    def test_non_cloudflare_ipv4_rejected(self):
        self.assertFalse(_cf_cache.contains('1.2.3.4'))

    def test_known_cloudflare_ipv6_accepted(self):
        # 2606:4700::1 is inside 2606:4700::/32
        self.assertTrue(_cf_cache.contains('2606:4700::1'))

    def test_non_cloudflare_ipv6_rejected(self):
        self.assertFalse(_cf_cache.contains('2001:db8::1'))

    def test_invalid_ip_string_returns_false(self):
        self.assertFalse(_cf_cache.contains('not-an-ip'))

    def test_loopback_not_cloudflare(self):
        self.assertFalse(_cf_cache.contains('127.0.0.1'))

class CloudflareMiddlewareTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

        def dummy_view(request):
            from django.http import HttpResponse
            return HttpResponse('ok')

        self.middleware = CloudflareSecurityMiddleware(dummy_view)

    @override_settings(DEBUG=False)
    def test_production_blocks_request_without_cf_header(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 403)

    @override_settings(DEBUG=False)
    def test_production_blocks_non_cloudflare_remote_addr(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        request.META['HTTP_CF_CONNECTING_IP'] = '8.8.8.8'
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 403)

    @override_settings(DEBUG=False)
    def test_production_allows_real_cloudflare_ip(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '104.16.0.1'
        request.META['HTTP_CF_CONNECTING_IP'] = '8.8.8.8'
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    @override_settings(DEBUG=True)
    def test_debug_mode_allows_any_ip(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    @override_settings(DEBUG=False)
    def test_localhost_always_allowed_in_production(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    @override_settings(DEBUG=False)
    def test_ipv6_localhost_always_allowed(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '::1'
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    def test_security_headers_added(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        resp = self.middleware(request)
        self.assertIn('Permissions-Policy', resp)
