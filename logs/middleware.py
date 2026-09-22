"""Her isteği aktivite logu kuyruğuna bırakan middleware."""

import logging
import time

from django.core.exceptions import MiddlewareNotUsed

from .logger import is_configured, record_request, setting

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
