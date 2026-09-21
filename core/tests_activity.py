"""Aktivite loglama testleri.

`manage.py test core.tests_activity` ile çalıştırılır (core/tests.py bu
değişiklikten bağımsız olarak zaten bozuk, o yüzden ayrı modül).

TransactionTestCase kullanılıyor: kayıtları arka plandaki writer thread
kendi bağlantısından yazdığı için satırların gerçekten commit edilmesi gerekir.
"""

from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from core import logger
from core.models import ActivityLog


@override_settings(ACTIVITY_LOG_ENABLED=True, ACTIVITY_LOG_FLUSH_SECONDS=0.05)
class ActivityLogTests(TransactionTestCase):

    def setUp(self):
        ActivityLog.objects.all().delete()

    def tearDown(self):
        logger.flush_now()
        ActivityLog.objects.all().delete()

    def drain(self):
        """Writer thread'i sentinel ile boşalt; kayıtlar commit edilsin."""
        logger.flush_now()

    def test_page_view_is_logged(self):
        self.client.get('/')
        self.drain()

        log = ActivityLog.objects.get()
        self.assertEqual(log.action, 'page_view')
        self.assertEqual(log.path, '/')
        self.assertEqual(log.method, 'GET')
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.username, '')

    def test_query_string_is_stored_separately(self):
        self.client.get('/api/words', {'page': 1, 'sort': 'date_desc'})
        self.drain()

        log = ActivityLog.objects.get()
        self.assertEqual(log.action, 'api')
        self.assertEqual(log.path, '/api/words')
        self.assertIn('sort=date_desc', log.query)

    def test_excluded_prefixes_are_not_logged(self):
        with override_settings(ACTIVITY_LOG_EXCLUDE_PREFIXES=('/api/',)):
            # Middleware ön ekleri __init__'te okur; yeni bir örnek kur.
            from core.middleware import ActivityLogMiddleware
            mw = ActivityLogMiddleware(lambda r: None)
            self.assertEqual(mw.exclude, ('/api/',))

        self.client.get('/static/js/app.js')
        self.drain()
        self.assertFalse(ActivityLog.objects.filter(path__startswith='/static/').exists())

    def test_login_and_logout_are_logged(self):
        User.objects.create_user(username='denek', password='Cok-Gizli-1234')

        self.client.force_login(User.objects.get(username='denek'))
        self.client.post('/api/logout')
        self.drain()

        logout_log = ActivityLog.objects.filter(action='logout').first()
        self.assertIsNotNone(logout_log)
        self.assertEqual(logout_log.username, 'denek')

    def test_authenticated_request_records_user(self):
        user = User.objects.create_user(username='kayitli', password='Cok-Gizli-1234')
        self.client.force_login(user)
        self.client.get('/api/profile')
        self.drain()

        log = ActivityLog.objects.filter(path='/api/profile').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user_id, user.pk)
        self.assertEqual(log.username, 'kayitli')

    def test_failed_login_is_logged_with_reason(self):
        self.client.post(
            '/api/login',
            data={'username': 'yokboyle', 'password': 'yanlis'},
            content_type='application/json',
        )
        self.drain()

        log = ActivityLog.objects.filter(path='/api/login').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, 'login_failed')
        self.assertEqual(log.status_code, 400)

    def test_bot_requests_are_flagged(self):
        self.client.get('/', headers={'user-agent': 'Googlebot/2.1 (+http://www.google.com/bot.html)'})
        self.drain()

        log = ActivityLog.objects.get()
        self.assertTrue(log.is_bot)

    def test_disabled_logging_writes_nothing(self):
        with override_settings(ACTIVITY_LOG_ENABLED=False):
            self.client.get('/')
            self.drain()
        self.assertEqual(ActivityLog.objects.count(), 0)

    def test_admin_changelist_renders(self):
        admin_user = User.objects.create_superuser(
            username='patron', email='', password='Cok-Gizli-1234'
        )
        self.client.force_login(admin_user)

        self.client.get('/')  # listede gösterilecek en az bir kayıt
        self.drain()

        response = self.client.get(reverse('admin:core_activitylog_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Son 24 saat')

    def test_prune_command_deletes_old_rows(self):
        from datetime import timedelta
        from django.core.management import call_command
        from django.utils import timezone

        ActivityLog.objects.create(path='/eski', timestamp=timezone.now() - timedelta(days=90))
        ActivityLog.objects.create(path='/yeni')

        call_command('prune_activity_logs', '--days', '30', verbosity=0)

        self.assertEqual(ActivityLog.objects.count(), 1)
        self.assertEqual(ActivityLog.objects.get().path, '/yeni')


@override_settings(ACTIVITY_LOG_ENABLED=True, ACTIVITY_LOG_FLUSH_SECONDS=0.05)
class ActivityLogRobustnessTests(TransactionTestCase):
    """Yazma hatalarına ve bozuk girdiye dayanıklılık."""

    def setUp(self):
        logger._paused_until = 0.0
        logger._pause_seconds = logger._PAUSE_MIN_SECONDS
        logger._consecutive_failures = 0
        ActivityLog.objects.all().delete()

    def tearDown(self):
        logger.flush_now()
        logger._paused_until = 0.0
        logger._pause_seconds = logger._PAUSE_MIN_SECONDS
        logger._consecutive_failures = 0
        ActivityLog.objects.all().delete()

    @staticmethod
    def _payload(**over):
        from django.utils import timezone
        payload = dict(
            timestamp=timezone.now(), action='page_view', user_id=None, username='',
            ip='1.2.3.4', method='GET', path='/x', query='', status_code=200,
            duration_ms=1, detail='', user_agent='', is_bot=False,
        )
        payload.update(over)
        return payload

    def test_forged_ip_header_is_rejected(self):
        """CF-Connecting-IP istemci kontrolünde; IP olmayan değer yazılmamalı."""
        self.client.get('/', headers={'cf-connecting-ip': 'NOT-AN-IP-' + 'x' * 200})
        logger.flush_now()

        log = ActivityLog.objects.get()
        self.assertIsNone(log.ip)

    def test_valid_forwarded_ip_is_kept(self):
        self.client.get('/', headers={'cf-connecting-ip': '198.51.100.7'})
        logger.flush_now()

        self.assertEqual(ActivityLog.objects.get().ip, '198.51.100.7')

    def test_overlong_action_is_truncated_to_field_length(self):
        from django.test import RequestFactory

        request = RequestFactory().get('/')
        logger.log_activity(request, 'a' * 80)
        self.assertEqual(
            len(logger._resolve_action(request, '/')), logger._ACTION_MAX_LENGTH
        )

    def test_one_bad_row_does_not_lose_the_batch(self):
        """Bozuk tek satır (var olmayan kullanıcıya FK) partiyi düşürmemeli."""
        for i in range(10):
            logger.enqueue(self._payload(path=f'/saglam{i}'))
        logger.enqueue(self._payload(path='/bozuk', user_id=999999))
        logger.flush_now()

        self.assertEqual(ActivityLog.objects.count(), 10)
        self.assertFalse(ActivityLog.objects.filter(path='/bozuk').exists())
        self.assertEqual(logger._consecutive_failures, 0)
        self.assertTrue(logger.is_enabled())

    def test_repeated_failures_pause_but_do_not_disable_forever(self):
        for _ in range(logger._MAX_CONSECUTIVE_FAILURES):
            logger.enqueue(self._payload(path='/bozuk', user_id=999999))
            logger.flush_now()

        # Ara verildi ama kalıcı değil.
        self.assertFalse(logger.is_enabled())
        self.assertGreater(logger._paused_until, 0.0)

        # Bekleme dolduğunda kendiliğinden devam eder.
        logger._paused_until = 0.0
        self.assertTrue(logger.is_enabled())
        self.client.get('/')
        logger.flush_now()
        self.assertTrue(ActivityLog.objects.filter(path='/').exists())

    def test_pause_backoff_doubles_then_resets_after_success(self):
        def trip():
            for _ in range(logger._MAX_CONSECUTIVE_FAILURES):
                logger.enqueue(self._payload(path='/bozuk', user_id=999999))
                logger.flush_now()

        trip()
        first = logger._pause_seconds
        logger._paused_until = 0.0
        trip()
        self.assertEqual(logger._pause_seconds, first * 2)

        logger._paused_until = 0.0
        logger.enqueue(self._payload(path='/saglam'))
        logger.flush_now()
        self.assertEqual(logger._pause_seconds, logger._PAUSE_MIN_SECONDS)
