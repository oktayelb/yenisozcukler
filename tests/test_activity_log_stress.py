"""Yük altında kayıt kaybı olmadığını doğrular.

Ayrı modül: `tests.test_activity_log` hızlı kalsın diye ayrıldı.
`manage.py test tests.test_activity_log_stress` ile çalıştırılır.
"""

import threading
import time

from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from core import logger
from core.models import ActivityLog


def _payload(path):
    return dict(
        timestamp=timezone.now(), action='page_view', user_id=None, username='',
        ip='198.51.100.7', method='GET', path=path, query='', status_code=200,
        duration_ms=1, detail='', user_agent='Mozilla/5.0',
    )


@override_settings(ACTIVITY_LOG_ENABLED=True, ACTIVITY_LOG_QUEUE_SIZE=200000)
class ActivityLogStressTests(TransactionTestCase):

    THREADS = 8
    PER_THREAD = 2000

    def setUp(self):
        logger._paused_until = 0.0
        logger._consecutive_failures = 0
        ActivityLog.objects.all().delete()

    def tearDown(self):
        logger.flush_now()
        ActivityLog.objects.all().delete()

    def test_no_row_is_lost_under_concurrent_load(self):
        """Kuyruk taşmadığı sürece yazılan satır sayısı üretilenle birebir."""
        total = self.THREADS * self.PER_THREAD

        def worker(n):
            for i in range(self.PER_THREAD):
                logger.enqueue(_payload(f'/t{n}/{i}'))

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(self.THREADS)]
        started = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        produced = time.perf_counter() - started

        logger.flush_now(timeout=60)
        written = ActivityLog.objects.count()

        self.assertEqual(written, total, f'{total - written} satır kayboldu')
        self.assertEqual(logger._dropped, 0)
        print(
            f'\n  {total} kayıt: istek thread\'leri {produced:.2f}s, '
            f'toplam {time.perf_counter() - started:.2f}s'
        )

    def test_full_queue_drops_rows_instead_of_blocking(self):
        """Kuyruk dolduğunda istek beklememeli: kayıt düşürülür, hata atılmaz."""
        with override_settings(ACTIVITY_LOG_QUEUE_SIZE=10):
            logger.flush_now()
            logger._queue = None       # yeni boyutla kurulsun
            logger._worker = None
            logger._dropped = 0

            # Writer'ı meşgul etmeden kuyruğu doldurmak için thread'i durduruyoruz.
            q = logger._ensure_worker()
            logger.flush_now()

            started = time.perf_counter()
            for i in range(500):
                logger.enqueue(_payload(f'/tasma{i}'))
            elapsed = time.perf_counter() - started

        # 500 kayıt 10'luk kuyruğa sığmaz; fazlası düşer ama hiç beklemez.
        self.assertLess(elapsed, 1.0)
        self.assertGreater(logger._dropped, 0)

        logger._dropped = 0
        logger._queue = None
        logger._worker = None
