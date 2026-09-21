import atexit
import ipaddress
import logging
import os
import queue
import random
import threading
import time
from datetime import timedelta

from decouple import config
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from .http import get_client_ip, is_bot

logger = logging.getLogger(__name__)

# --- Ayarlar ------------------------------------------------------------------
# Aktivite logunun tüm yapılandırması burada durur; settings.py'ye dağılmaz.
# Değerler .env'den okunur, testler `override_settings` ile ezebilir
# (bkz. `setting`).
_DEFAULTS = {
    # Kill switch: kapalıysa ne middleware ne writer thread çalışır.
    'ACTIVITY_LOG_ENABLED': config('ACTIVITY_LOG_ENABLED', default=True, cast=bool),
    # Kuyruk dolarsa kayıtlar düşürülür — istek asla bloklanmaz.
    'ACTIVITY_LOG_QUEUE_SIZE': config('ACTIVITY_LOG_QUEUE_SIZE', default=5000, cast=int),
    # Kaç kayıt birikince tek INSERT ile yazılsın.
    'ACTIVITY_LOG_BATCH_SIZE': config('ACTIVITY_LOG_BATCH_SIZE', default=100, cast=int),
    # Batch dolmasa da en geç bu kadar saniyede bir yaz.
    'ACTIVITY_LOG_FLUSH_SECONDS': config('ACTIVITY_LOG_FLUSH_SECONDS', default=2.0, cast=float),
    # Bu günden eski kayıtlar otomatik silinir (0 = hiç silme).
    'ACTIVITY_LOG_RETENTION_DAYS': config('ACTIVITY_LOG_RETENTION_DAYS', default=30, cast=int),
    # Saklama süresi kontrolünün writer thread'inde tekrarlanma aralığı.
    'ACTIVITY_LOG_PRUNE_SECONDS': 3600,
    # Bu ön ekle başlayan yollar hiç loglanmaz.
    'ACTIVITY_LOG_EXCLUDE_PREFIXES': ('/static/', '/favicon.ico'),
}

_SENTINEL = object()

# Kuyruk + writer thread durumu (process başına)
_queue = None
_worker = None
_worker_pid = None
_lock = threading.Lock()

# Kuyruk dolduğunda düşürülen kayıt sayısı (uyarı log'u için)
_dropped = 0
_last_drop_warning = 0.0

# Art arda yazma hatası olursa loglamaya ara ver (ör. tablo henüz yoksa,
# DB kilitli, bakım vs.). Kalıcı kapatma yok: her aradan sonra yeniden denenir,
# bekleme süresi hata devam ettikçe ikiye katlanır.
_consecutive_failures = 0
_MAX_CONSECUTIVE_FAILURES = 5
_PAUSE_MIN_SECONDS = 60.0
_PAUSE_MAX_SECONDS = 3600.0
_paused_until = 0.0
_pause_seconds = _PAUSE_MIN_SECONDS

# Bozuk bir satır yüzünden partinin tamamı kaybolmasın diye hata durumunda
# parti ikiye bölünerek yeniden denenir. DB tamamen kapalıysa bu kurtarma
# boşuna uğraşmasın diye hem deneme hem süre sınırı var.
_SALVAGE_MAX_ATTEMPTS = 32
_SALVAGE_SECONDS = 5.0

# GenericIPAddressField 39 karaktere kadar saklar.
_IP_MAX_LENGTH = 39
# ActivityLog.action alanının max_length'i.
_ACTION_MAX_LENGTH = 24


def setting(name):
    """Ayarı döndürür: varsa Django ayarı, yoksa buradaki varsayılan.

    settings.py'de bu isimler tanımlı değil; getattr yalnızca testlerdeki
    `override_settings` için var.
    """
    return getattr(settings, name, _DEFAULTS[name])


def is_enabled():
    if not setting('ACTIVITY_LOG_ENABLED'):
        return False
    # Yazma hataları yüzünden verilen ara dolduysa kendiliğinden devam eder.
    return _paused_until <= time.monotonic()


# --- View'lardan çağrılan yardımcı -------------------------------------------

def log_activity(request, action=None, detail=None, username=None, set_default=False):
    """İstek üzerine ek bağlam işaretler; asıl satırı middleware yazar.

    DB'ye dokunmaz, sadece request nesnesine attribute koyar.
    `set_default=True` ise eylem yalnızca henüz belirlenmemişse yazılır
    (sinyallerden gelen genel bilgiler için).
    """
    # DRF Request ise alttaki HttpRequest'e yaz — middleware onu görür.
    req = getattr(request, '_request', request)
    if req is None:
        return
    if action is not None:
        if not (set_default and getattr(req, '_activity_action', None)):
            req._activity_action = str(action)[:_ACTION_MAX_LENGTH]
    if detail is not None:
        req._activity_detail = str(detail)[:200]
    if username is not None:
        req._activity_username = str(username)[:150]


# --- URL adı -> eylem eşlemesi ------------------------------------------------

URL_ACTION_MAP = {
    'login': 'login',
    'register': 'register',
    'logout': 'logout',
    'add_word': 'word_add',
    'add_comment': 'comment_add',
    'vote': 'vote',
    'add_example': 'example_add',
    'change_password': 'password_change',
    'change_username': 'username_change',
    'mark_notifications_read': 'notifications_read',
}


def _resolve_action(request, path):
    explicit = getattr(request, '_activity_action', None)
    if explicit:
        return str(explicit)[:_ACTION_MAX_LENGTH]

    match = getattr(request, 'resolver_match', None)
    if match is not None:
        mapped = URL_ACTION_MAP.get(match.url_name)
        if mapped:
            return mapped
        if (match.app_names and 'admin' in match.app_names) or \
                (match.namespaces and 'admin' in match.namespaces):
            return 'admin'

    if path.startswith('/api/'):
        return 'api'
    return 'page_view'


def _clean_ip(value):
    """Başlıktan gelen IP'yi doğrular. Writer thread'inde çalışır.

    `get_client_ip` CF-Connecting-IP / X-Forwarded-For başlıklarını olduğu gibi
    döndürür ve bu başlıklar istemci kontrolündedir (ActivityLogMiddleware
    Cloudflare kontrolünün de dışında olduğu için engellenen istekler de buraya
    düşer). Doğrulanmadan yazılırsa SQLite'ta çöp veri, Postgres'te ise `inet`
    sütunu DataError verip partinin tamamını düşürür.

    `ipaddress` ayrıştırması istek başına birkaç mikrosaniye tuttuğu için
    istek thread'inde değil, arka plandaki `_flush` içinde yapılır.
    """
    if not value:
        return None
    try:
        cleaned = str(ipaddress.ip_address(value.strip()))
    except (ValueError, AttributeError):
        return None
    return cleaned if len(cleaned) <= _IP_MAX_LENGTH else None


# --- Middleware'in çağırdığı kayıt fonksiyonu ---------------------------------

def record_request(request, response, duration_ms):
    if not is_enabled():
        return
    try:
        username = getattr(request, '_activity_username', '')
        user_id = None
        # Oturum çerezi yoksa ziyaretçi kesinlikle anonimdir: request.user'a
        # dokunmayıp gereksiz session sorgusundan kaçınıyoruz.
        if settings.SESSION_COOKIE_NAME in request.COOKIES:
            user = getattr(request, 'user', None)
            if user is not None and user.is_authenticated:
                user_id = user.pk
                if not username:
                    username = user.get_username()

        ua = request.META.get('HTTP_USER_AGENT', '') or ''
        path = request.path

        payload = {
            'timestamp': timezone.now(),
            'action': _resolve_action(request, path),
            'user_id': user_id,
            'username': (username or '')[:150],
            # Doğrulama writer thread'inde (_flush -> _clean_ip); burada
            # sadece kuyruğun şişmemesi için ham değer kısaltılır.
            'ip': (get_client_ip(request) or '')[:64],
            'method': request.method[:8] if request.method else '',
            'path': path[:300],
            'query': request.META.get('QUERY_STRING', '')[:200],
            'status_code': getattr(response, 'status_code', 0) or 0,
            'duration_ms': duration_ms,
            'detail': getattr(request, '_activity_detail', '')[:200],
            'user_agent': ua[:200],
            'is_bot': is_bot(ua),
        }
    except Exception:
        logger.warning('activity log payload build failed', exc_info=True)
        return

    enqueue(payload)


def enqueue(payload):
    global _dropped, _last_drop_warning
    try:
        q = _ensure_worker()
        q.put_nowait(payload)
    except queue.Full:
        _dropped += 1
        now = time.monotonic()
        if now - _last_drop_warning > 60:
            _last_drop_warning = now
            logger.warning('activity log queue full, %d kayıt düşürüldü', _dropped)
    except Exception:
        logger.warning('activity log enqueue failed', exc_info=True)


# --- Writer thread ------------------------------------------------------------

def _ensure_worker():
    global _queue, _worker, _worker_pid
    pid = os.getpid()
    worker = _worker
    if worker is not None and _worker_pid == pid and worker.is_alive():
        return _queue

    with _lock:
        if _worker is not None and _worker_pid == pid and _worker.is_alive():
            return _queue
        if _queue is None or _worker_pid != pid:
            # Fork sonrası miras alınan kuyruk tutarsız olabilir; yenisini kur.
            _queue = queue.Queue(maxsize=setting('ACTIVITY_LOG_QUEUE_SIZE'))
            atexit.register(_shutdown)
        _worker_pid = pid
        _worker = threading.Thread(
            target=_run, args=(_queue,), name='activity-log-writer', daemon=True
        )
        _worker.start()
        return _queue


def _run(q):
    batch_size = setting('ACTIVITY_LOG_BATCH_SIZE')
    flush_seconds = setting('ACTIVITY_LOG_FLUSH_SECONDS')
    batch = []
    deadline = None
    next_prune = time.monotonic() + random.uniform(60, 300)

    while True:
        # Boşta beklerken de saklama süresi kontrolü yapılabilsin diye
        # timeout hiçbir zaman sonsuz değil.
        if deadline is None:
            timeout = 60.0
        else:
            timeout = max(0.0, deadline - time.monotonic())

        try:
            item = q.get(timeout=timeout)
        except queue.Empty:
            item = None

        if item is _SENTINEL:
            _flush(batch)
            return

        if item is None:
            _flush(batch)
            deadline = None
        else:
            batch.append(item)
            if deadline is None:
                deadline = time.monotonic() + flush_seconds
            if len(batch) >= batch_size:
                _flush(batch)
                deadline = None

        if time.monotonic() >= next_prune:
            next_prune = time.monotonic() + setting('ACTIVITY_LOG_PRUNE_SECONDS')
            _prune()


def _on_write_success():
    """En az bir satır yazıldı: DB ayakta, sayaç ve bekleme süresi sıfırlanır."""
    global _consecutive_failures, _pause_seconds
    _consecutive_failures = 0
    _pause_seconds = _PAUSE_MIN_SECONDS


def _on_write_failure(exc):
    """Hiçbir satır yazılamadı; üst üste yeterince olursa loglamaya ara ver."""
    global _consecutive_failures, _paused_until, _pause_seconds
    _consecutive_failures += 1
    logger.warning('activity log flush failed (%d): %s', _consecutive_failures, exc)
    if _consecutive_failures < _MAX_CONSECUTIVE_FAILURES:
        return
    _paused_until = time.monotonic() + _pause_seconds
    logger.error(
        'activity log %.0f saniye duraklatıldı (art arda %d yazma hatası)',
        _pause_seconds, _consecutive_failures,
    )
    # Hata sürerse bekleme ikiye katlanır; düzelirse _on_write_success sıfırlar.
    _pause_seconds = min(_pause_seconds * 2, _PAUSE_MAX_SECONDS)
    _consecutive_failures = 0


def _insert(rows, budget):
    """Satırları yazar; hata olursa partiyi ikiye bölerek yeniden dener.

    Tek bir bozuk satır (ör. silinmiş kullanıcıya FK) yüzünden partinin tamamı
    kaybolmasın diye. DB tamamen kapalıysa boşuna uğraşmamak için `budget`
    hem deneme sayısını hem geçen süreyi sınırlar; sınır dolunca kalan satırlar
    düşürülür.

    Dönüş: (yazılan, düşürülen).
    """
    from .models import ActivityLog

    if not rows:
        return 0, 0

    budget['attempts'] += 1
    try:
        ActivityLog.objects.bulk_create(rows, batch_size=200)
        return len(rows), 0
    except Exception as exc:
        budget['error'] = exc
        if len(rows) == 1:
            logger.warning('activity log satırı yazılamadı, düşürüldü: %s', exc)
            return 0, 1
        # DB tamamen kapalıysa bölmenin faydası yok: sınırı aşınca vazgeç.
        if budget['attempts'] >= _SALVAGE_MAX_ATTEMPTS or \
                time.monotonic() >= budget['deadline']:
            return 0, len(rows)

    mid = len(rows) // 2
    ok_a, bad_a = _insert(rows[:mid], budget)
    ok_b, bad_b = _insert(rows[mid:], budget)
    return ok_a + ok_b, bad_a + bad_b


def _flush(batch):
    if not batch:
        return

    from .models import ActivityLog

    rows = []
    for item in batch:
        item['ip'] = _clean_ip(item['ip'])
        rows.append(ActivityLog(**item))
    batch.clear()
    budget = {
        'attempts': 0,
        'deadline': time.monotonic() + _SALVAGE_SECONDS,
        'error': None,
    }
    try:
        written, dropped = _insert(rows, budget)
        if dropped:
            logger.warning('activity log: %d satır kurtarılamadı', dropped)
        if written:
            _on_write_success()
        elif budget['error'] is not None:
            _on_write_failure(budget['error'])
    except Exception as exc:
        # _insert dışında beklenmedik bir hata (ör. model import'u).
        _on_write_failure(exc)
    finally:
        # CONN_MAX_AGE'e uy: bu thread'in SQLite bağlantısını boşta tutma.
        close_old_connections()


def _prune():
    """Saklama süresini aşan kayıtları parça parça siler."""
    days = setting('ACTIVITY_LOG_RETENTION_DAYS')
    if not days:
        return

    from .models import ActivityLog

    cutoff = timezone.now() - timedelta(days=days)
    try:
        while True:
            ids = list(
                ActivityLog.objects.filter(timestamp__lt=cutoff)
                .values_list('id', flat=True)[:2000]
            )
            if not ids:
                break
            ActivityLog.objects.filter(id__in=ids).delete()
            if len(ids) < 2000:
                break
    except Exception as exc:
        logger.warning('activity log prune failed: %s', exc)
    finally:
        close_old_connections()


def _shutdown(timeout=5):
    """Process kapanırken kuyrukta kalanları yaz."""
    q, worker = _queue, _worker
    if q is None or worker is None or not worker.is_alive():
        return
    try:
        q.put_nowait(_SENTINEL)
    except queue.Full:
        return
    worker.join(timeout=timeout)


def flush_now(timeout=5):
    """Testler/komutlar için: kuyruğu boşalt.

    Writer thread sentinel'i görüp durur; bir sonraki `enqueue` onu
    `_ensure_worker` üzerinden yeniden başlatır.
    """
    _shutdown(timeout)
