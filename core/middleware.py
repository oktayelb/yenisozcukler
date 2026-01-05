# core/middleware.py
from django.http import HttpResponseForbidden
from django.conf import settings

class CloudflareSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Kendi bilgisayarından (Localhost) gelen isteklere her zaman izin ver
        # Geliştirme yaparken kendini engellememen için bu şart.
        remote_addr = request.META.get('REMOTE_ADDR')
        if remote_addr in ['127.0.0.1', '::1']:
            return self.get_response(request)

        # 2. DEBUG modu açıksa (geliştirme aşaması) izin verilebilir
        # Amaç canlıya (prodüksiyon) geçince korumak olduğu için burayı
        # production'da False yapacağın varsayılır.
        if settings.DEBUG:
             # İsteğe bağlı: Test ederken kapatmak istersen burayı silebilirsin.
            return self.get_response(request)

        # 3. Cloudflare Başlığı Kontrolü
        # Cloudflare'den gelen her istekte bu başlık mutlaka olur.
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')

        if not cf_ip:
            # Başlık yoksa, istek Cloudflare üzerinden gelmiyor demektir.
            # Direkt IP'ye saldırı yapılıyordur. Engelle!
            return HttpResponseForbidden("Erisim Engellendi: Sadece Cloudflare üzerinden erisilebilir.")

        return self.get_response(request)