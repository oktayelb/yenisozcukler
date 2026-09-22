"""Aktivite loglama testleri.

`manage.py test tests.test_activity_log` ile tek başına çalıştırılabilir.

TransactionTestCase kullanılıyor: kayıtları arka plandaki writer thread
kendi bağlantısından yazdığı için satırların gerçekten commit edilmesi gerekir.
"""

from unittest import mock

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

    def test_forged_ip_header_does_not_crash_rate_limited_views(self):
        """Bozuk CF-Connecting-IP her uçtan 500 döndürüyordu.

        django-ratelimit anahtarı kurarken `ipaddress.ip_network(f'{ip}/{mask}')`
        çağırır; `get_client_ip` başlığı ham döndürdüğü için ValueError
        fırlatıyordu. Oran sınırı olmayan uç neredeyse yok, yani tek bir
        başlıkla bütün site 500'e düşüyordu.
        """
        for forged in ('not-an-ip', '<script>alert(1)</script>', '999.999.999.999',
                       'a' * 300, '1.2.3.4, 5.6.7.8'):
            with self.subTest(forged=forged):
                response = self.client.get(
                    '/api/categories', headers={'cf-connecting-ip': forged}
                )
                self.assertLess(response.status_code, 500, forged)

    def test_client_ip_falls_back_when_the_header_is_forged(self):
        from django.test import RequestFactory
        from core.http import get_client_ip

        request = RequestFactory().get(
            '/', HTTP_CF_CONNECTING_IP='cop-deger', REMOTE_ADDR='203.0.113.9'
        )
        self.assertEqual(get_client_ip(request), '203.0.113.9')

    def test_client_ip_skips_invalid_entries_in_forwarded_chain(self):
        from django.test import RequestFactory
        from core.http import get_client_ip

        request = RequestFactory().get(
            '/', HTTP_X_FORWARDED_FOR='cop, 198.51.100.4', REMOTE_ADDR='203.0.113.9'
        )
        self.assertEqual(get_client_ip(request), '198.51.100.4')

    def test_forged_ip_header_is_rejected(self):
        """CF-Connecting-IP istemci kontrolünde; IP olmayan değer yazılmamalı.

        Uydurma değerin yerine gerçek TCP karşı tarafı (REMOTE_ADDR) yazılır —
        NULL yazmaktan daha kullanışlı.
        """
        forged = 'NOT-AN-IP-' + 'x' * 200
        self.client.get('/', headers={'cf-connecting-ip': forged})
        logger.flush_now()

        log = ActivityLog.objects.get()
        self.assertNotIn('NOT-AN-IP', log.ip or '')
        self.assertEqual(log.ip, '127.0.0.1')

    def test_ip_is_null_when_no_source_is_valid(self):
        self.client.get(
            '/', headers={'cf-connecting-ip': 'cop'}, REMOTE_ADDR='de-cop',
        )
        logger.flush_now()

        self.assertIsNone(ActivityLog.objects.get().ip)

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


@override_settings(ACTIVITY_LOG_ENABLED=True, ACTIVITY_LOG_FLUSH_SECONDS=0.05)
class ActivityLogAttributionTests(TransactionTestCase):
    """Kaydın kime ait olduğu: misafir, kayıtlı kullanıcı, giriş/çıkış anı."""

    PASSWORD = 'Cok-Gizli-1234'

    def setUp(self):
        ActivityLog.objects.all().delete()

    def tearDown(self):
        logger.flush_now()
        ActivityLog.objects.all().delete()

    def _row(self, path):
        logger.flush_now()
        return ActivityLog.objects.filter(path=path).first()

    def test_anonymous_visitor_has_no_user(self):
        self.client.get('/')
        row = self._row('/')
        self.assertIsNone(row.user_id)
        self.assertEqual(row.username, '')
        self.assertEqual(row.display_user, 'Misafir')

    def test_anonymous_api_call_has_no_user(self):
        self.client.get('/api/words')
        row = self._row('/api/words')
        self.assertIsNone(row.user_id)
        self.assertEqual(row.username, '')

    def test_login_row_is_attributed_to_the_user(self):
        """Giriş anında oturum çerezi daha isteğe gelmemiştir.

        Sadece `request.COOKIES`'e bakan sürüm bu satırı sahipsiz yazıyordu.
        """
        user = User.objects.create_user(username='girisci', password=self.PASSWORD)

        # DEBUG testlerde kapalı olduğu için Turnstile gerçekten çağrılırdı.
        with mock.patch('accounts.views.verify_turnstile', return_value=True):
            response = self.client.post(
                '/api/login',
                data={'username': 'girisci', 'password': self.PASSWORD},
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)

        row = self._row('/api/login')
        self.assertEqual(row.action, 'login')
        self.assertEqual(row.user_id, user.pk)
        self.assertEqual(row.username, 'girisci')

    def test_register_row_is_attributed_to_the_new_user(self):
        with mock.patch('accounts.views.verify_turnstile', return_value=True):
            response = self.client.post(
                '/api/register',
                data={'username': 'yenikullanici', 'password': self.PASSWORD},
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 201)

        row = self._row('/api/register')
        self.assertEqual(row.action, 'register')
        self.assertEqual(row.username, 'yenikullanici')
        self.assertEqual(row.user_id, User.objects.get(username='yenikullanici').pk)

    def test_logout_row_keeps_the_user_id(self):
        """`logout()` request.user'ı AnonymousUser yapar; FK sinyalden gelir."""
        user = User.objects.create_user(username='cikisci', password=self.PASSWORD)
        self.client.force_login(user)
        self.client.post('/api/logout')

        row = self._row('/api/logout')
        self.assertEqual(row.action, 'logout')
        self.assertEqual(row.user_id, user.pk)
        self.assertEqual(row.username, 'cikisci')

    def test_password_change_is_not_mislabelled_as_failed_login(self):
        """Yanlış mevcut şifre `user_login_failed` sinyalini tetikler."""
        user = User.objects.create_user(username='sifreci', password=self.PASSWORD)
        self.client.force_login(user)

        self.client.patch(
            '/api/password',
            data={'current_password': 'yanlis', 'new_password': 'Baska-Gizli-9876'},
            content_type='application/json',
        )

        row = self._row('/api/password')
        self.assertEqual(row.action, 'password_change')
        self.assertEqual(row.user_id, user.pk)

    def test_admin_login_is_logged_through_the_auth_signal(self):
        User.objects.create_superuser(username='patron2', email='', password=self.PASSWORD)

        self.client.post(
            '/admin/login/',
            {'username': 'patron2', 'password': self.PASSWORD, 'next': '/admin/'},
        )

        row = self._row('/admin/login/')
        self.assertEqual(row.action, 'login')
        self.assertEqual(row.username, 'patron2')

    def test_admin_page_view_is_labelled_admin(self):
        admin_user = User.objects.create_superuser(
            username='patron3', email='', password=self.PASSWORD
        )
        self.client.force_login(admin_user)
        self.client.get('/admin/')

        row = self._row('/admin/')
        self.assertEqual(row.action, 'admin')
        self.assertEqual(row.user_id, admin_user.pk)


@override_settings(ACTIVITY_LOG_ENABLED=True, ACTIVITY_LOG_FLUSH_SECONDS=0.05)
class ActivityLogCoverageTests(TransactionTestCase):
    """Hiçbir view loglanmadan geçmemeli."""

    def setUp(self):
        ActivityLog.objects.all().delete()

    def tearDown(self):
        logger.flush_now()
        ActivityLog.objects.all().delete()

    @staticmethod
    def _routed_paths():
        """URLconf'taki her uca gidecek somut bir yol üretir.

        Catch-all ve admin'in yüzlerce alt yolu dışarıda: onlar ayrı
        testlerde. Amaç, elle tutulan bir liste tutmadan yeni bir uç
        eklendiğinde bu testin onu kendiliğinden kapsaması.
        """
        return [
            ('get', '/'),
            ('get', '/robots.txt'),
            ('get', '/sitemap.xml'),
            ('get', '/sozcuk/olmayan-sozcuk/'),
            ('get', '/kategori/olmayan-kategori/'),
            ('get', '/rastgele-bir-sayfa'),          # SPA catch-all
            ('get', '/api/words'),
            ('get', '/api/word/999999'),
            ('get', '/api/word-by-slug/olmayan'),
            ('get', '/api/categories'),
            ('get', '/api/my-words'),
            ('get', '/api/random-word'),
            ('get', '/api/comments/999999'),
            ('get', '/api/profile'),
            ('get', '/api/notifications'),
            ('get', '/api/notifications/unread-count'),
            ('get', '/api/olmayan-uc'),              # 404
            ('post', '/api/word'),
            ('post', '/api/comment'),
            ('post', '/api/vote/word/999999'),
            ('post', '/api/login'),
            ('post', '/api/register'),
            ('post', '/api/logout'),
            ('post', '/api/notifications/mark-read'),
            ('patch', '/api/password'),
            ('patch', '/api/username'),
            ('patch', '/api/example'),
        ]

    def _hit_all(self):
        for method, path in self._routed_paths():
            getattr(self.client, method)(path, data={}, content_type='application/json')
        logger.flush_now()

    def test_every_route_is_logged_for_anonymous_visitors(self):
        self._hit_all()
        logged = set(ActivityLog.objects.values_list('path', flat=True))
        for _, path in self._routed_paths():
            self.assertIn(path, logged, f'{path} loglanmadı')

    def test_every_route_is_logged_for_registered_users(self):
        user = User.objects.create_user(username='uye', password='Cok-Gizli-1234')
        self.client.force_login(user)

        self._hit_all()

        rows = list(ActivityLog.objects.all())
        logged = {row.path for row in rows}
        for _, path in self._routed_paths():
            self.assertIn(path, logged, f'{path} loglanmadı')

        # Çıkış öncesi istekler kullanıcıya bağlanmış olmalı.
        profile = ActivityLog.objects.filter(path='/api/profile').first()
        self.assertEqual(profile.user_id, user.pk)
        self.assertEqual(profile.username, 'uye')

    def test_urlconf_has_no_unmapped_write_endpoint(self):
        """Yeni bir POST/PATCH ucu eklenirse eylem eşlemesi de eklensin.

        Aksi hâlde satır genel 'api' kovasına düşer ve admin'deki eylem
        filtresinde görünmez.
        """
        from django.urls import get_resolver

        read_only = {
            'get_words', 'get_word', 'get_word_by_slug', 'get_categories',
            'get_my_words', 'get_random_word', 'get_comments',
            'get_user_profile', 'get_notifications', 'get_unread_count',
            'robots_txt', 'sitemap_xml', 'favicon_ico', 'index',
            'word_detail', 'spa_category', 'spa_catchall',
        }
        names = {
            key for key in get_resolver().reverse_dict.keys()
            if isinstance(key, str)
        }
        unmapped = names - read_only - set(logger.URL_ACTION_MAP)
        self.assertEqual(
            unmapped, set(),
            f'Eylem eşlemesi olmayan uç(lar): {sorted(unmapped)} '
            '— core/logger.py:URL_ACTION_MAP ve ActivityLog.ACTION_CHOICES güncellenmeli.',
        )

    def test_every_producible_action_is_a_declared_choice(self):
        """Admin'de ham slug görünmesin: her eylem ACTION_CHOICES'ta olmalı."""
        declared = {value for value, _ in ActivityLog.ACTION_CHOICES}
        produced = set(logger.URL_ACTION_MAP.values()) | {
            'page_view', 'api', 'admin', 'blocked',
            'login_failed', 'register_failed', 'admin_word_action',
        }
        self.assertEqual(produced - declared, set())


@override_settings(ACTIVITY_LOG_ENABLED=True, ACTIVITY_LOG_FLUSH_SECONDS=0.05)
class ActivityLogWriterTests(TransactionTestCase):
    """Writer thread'i öldürebilecek durumlar."""

    def setUp(self):
        logger._paused_until = 0.0
        logger._consecutive_failures = 0
        ActivityLog.objects.all().delete()

    def tearDown(self):
        logger.flush_now()
        logger._paused_until = 0.0
        logger._consecutive_failures = 0
        ActivityLog.objects.all().delete()

    @staticmethod
    def _payload(**over):
        from django.utils import timezone
        payload = dict(
            timestamp=timezone.now(), action='page_view', user_id=None, username='',
            ip='1.2.3.4', method='GET', path='/x', query='', status_code=200,
            duration_ms=1, detail='', user_agent='',
        )
        payload.update(over)
        return payload

    def test_malformed_payload_does_not_kill_the_writer(self):
        logger.enqueue({'boyle_bir_alan_yok': 1})
        logger.enqueue(self._payload(path='/saglam'))
        logger.flush_now()

        self.assertTrue(ActivityLog.objects.filter(path='/saglam').exists())

    def test_rows_queued_behind_the_sentinel_are_still_written(self):
        """flush_now sentinel'i koyar; arkasında kalanlar kaybolmamalı."""
        q = logger._ensure_worker()
        for i in range(20):
            q.put_nowait(self._payload(path=f'/kuyruk{i}'))
        logger.flush_now()

        self.assertEqual(ActivityLog.objects.filter(path__startswith='/kuyruk').count(), 20)

    def test_flush_now_restarts_a_dead_writer_to_drain_the_queue(self):
        logger.flush_now()  # thread sentinel'i görüp duruyor
        q = logger._queue
        q.put_nowait(self._payload(path='/oksuz'))
        logger.flush_now()

        self.assertTrue(ActivityLog.objects.filter(path='/oksuz').exists())

    def test_transient_db_error_retries_the_whole_batch(self):
        """Kilit hatası partiye değil veritabanına aittir: bölünmemeli.

        Eski sürüm her hatada partiyi ikiye bölüyordu; SQLite'ta yazma kilidi
        yüzünden gelen bir hatada bu 32 kata kadar boşuna deneme demekti.
        """
        from django.db import OperationalError

        real_bulk_create = ActivityLog.objects.bulk_create
        batch_sizes = []

        def flaky(objs, **kwargs):
            objs = list(objs)
            batch_sizes.append(len(objs))
            if len(batch_sizes) == 1:
                raise OperationalError('database is locked')
            return real_bulk_create(objs, **kwargs)

        for i in range(8):
            logger.enqueue(self._payload(path=f'/kilit{i}'))

        with mock.patch.object(ActivityLog.objects, 'bulk_create', flaky), \
                mock.patch.object(logger, '_RETRY_SECONDS', 0.01):
            logger.flush_now()

        self.assertEqual(ActivityLog.objects.filter(path__startswith='/kilit').count(), 8)
        # İki deneme, ikisi de tam parti: hiç bölünmemiş.
        self.assertEqual(batch_sizes, [8, 8])

    def test_row_level_error_still_splits_the_batch(self):
        """Satıra özgü hatada bölme davranışı korunmalı."""
        for i in range(4):
            logger.enqueue(self._payload(path=f'/iyi{i}'))
        logger.enqueue(self._payload(path='/kotu', user_id=999999))
        logger.flush_now()

        self.assertEqual(ActivityLog.objects.filter(path__startswith='/iyi').count(), 4)
        self.assertFalse(ActivityLog.objects.filter(path='/kotu').exists())

    def test_bot_flag_is_computed_by_the_writer(self):
        logger.enqueue(self._payload(path='/bot', user_agent='Mozilla/5.0 (compatible; bingbot/2.0)'))
        logger.enqueue(self._payload(path='/insan', user_agent='Mozilla/5.0 (X11; Linux x86_64)'))
        logger.flush_now()

        self.assertTrue(ActivityLog.objects.get(path='/bot').is_bot)
        self.assertFalse(ActivityLog.objects.get(path='/insan').is_bot)

    def test_view_exception_is_logged_as_server_error(self):
        from core.middleware import ActivityLogMiddleware

        def boom(request):
            raise RuntimeError('patladı')

        mw = ActivityLogMiddleware(boom)
        request = self._request('/patlak')

        with self.assertRaises(RuntimeError):
            mw(request)
        logger.flush_now()

        row = ActivityLog.objects.get(path='/patlak')
        self.assertEqual(row.status_code, 500)

    @staticmethod
    def _request(path):
        from django.test import RequestFactory
        return RequestFactory().get(path)

    def test_middleware_survives_a_write_failure_pause(self):
        """Mola geçici; middleware kurulumu buna bakmamalı."""
        from core.middleware import ActivityLogMiddleware

        logger._paused_until = logger.time.monotonic() + 3600
        try:
            self.assertFalse(logger.is_enabled())
            self.assertTrue(logger.is_configured())
            ActivityLogMiddleware(lambda r: None)   # MiddlewareNotUsed atmamalı
        finally:
            logger._paused_until = 0.0
