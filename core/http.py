
import ipaddress
import json
import logging

import requests as http_requests
from decouple import config
from django.conf import settings

logger = logging.getLogger(__name__)


def verify_turnstile(token):
    if settings.DEBUG:
        return True
    if not token:
        return False
    try:
        resp = http_requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={'secret': config('CLOUDFLARE_SECRET_KEY'), 'response': token},
            timeout=5,
        )
        result = resp.json()
        if not result.get('success', False):
            logger.warning('Turnstile rejected: %s', result.get('error-codes', []))
        return result.get('success', False)
    except http_requests.RequestException as e:
        logger.error('Turnstile request failed: %s', e)
        return False


# GenericIPAddressField 39 karaktere kadar saklar.
IP_MAX_LENGTH = 39


def clean_ip(value):
    """Gerçek bir IP ise normalleştirilmiş hâlini, değilse None döndürür.

    `CF-Connecting-IP` ve `X-Forwarded-For` istemci kontrolündedir. Ham hâlde
    kullanılırsa:

    * django-ratelimit `ipaddress.ip_network(f'{ip}/{mask}')` çağırır ve
      ValueError fırlatır — tek bir bozuk başlık, oran sınırı olan her uçtan
      (yani neredeyse hepsinden) 500 döndürür;
    * `ip_address` alanları GenericIPAddressField'dır, Postgres'te `inet`
      sütununa çöp yazmak DataError verir.
    """
    if not value:
        return None
    try:
        cleaned = str(ipaddress.ip_address(value.strip()))
    except (ValueError, AttributeError):
        return None
    return cleaned if len(cleaned) <= IP_MAX_LENGTH else None


def get_client_ip(request):
    """İstemcinin doğrulanmış IP'si; hiçbiri geçerli değilse None.

    Sonuç istek nesnesinde saklanır: aynı istekte hem oran sınırı anahtarı,
    hem view, hem de aktivite logu bunu çağırıyor.
    """
    req = getattr(request, '_request', request)
    cached = getattr(req, '_client_ip_cache', False)
    if cached is not False:
        return cached

    ip = clean_ip(req.META.get('HTTP_CF_CONNECTING_IP'))
    if ip is None:
        forwarded = req.META.get('HTTP_X_FORWARDED_FOR') or ''
        for candidate in forwarded.split(','):
            ip = clean_ip(candidate)
            if ip is not None:
                break
    if ip is None:
        ip = clean_ip(req.META.get('REMOTE_ADDR'))

    try:
        req._client_ip_cache = ip
    except AttributeError:      # pragma: no cover - alışılmadık request nesnesi
        pass
    return ip


def universal_rate_key(group, request):
    if hasattr(request, 'user') and request.user.is_authenticated:
        return f"user_{request.user.id}"
    return f"ip_{get_client_ip(request)}"


def login_username_key(group, request):
    """Rate-limit key that reads username from JSON body (not request.POST)."""
    username = ''
    try:
        body = json.loads(request.body)
        username = body.get('username', '').strip().lower()
    except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
        username = request.POST.get('username', '').strip().lower()
    return username or get_client_ip(request)


# --- BOT TESPİTİ ---

BOT_SPECIFIC = [
    'googlebot', 'googlebot-image', 'google-inspectiontool',
    'oai-searchbot', 'chatgpt-user',
    'bingbot', 'yandexbot', 'duckduckbot', 'baiduspider',
    'slurp', 'facebookexternalhit', 'linkedinbot',
    'whatsapp', 'telegrambot', 'discordbot', 'applebot',
]
BOT_GENERIC = ['bot', 'crawler', 'spider', 'scraper', 'preview']


def is_bot(ua):
    """User-Agent'a bakarak tarayıcı mı bot mu ayırır.

    `seo` (dinamik render) ve `logger` (aktivite logu) aynı kararı verdiği için
    burada duruyor: `http.py` hiçbir model import etmez, ikisi de çekinmeden
    import edebilir.
    """
    ua = (ua or '').lower()
    return any(p in ua for p in BOT_SPECIFIC) or any(p in ua for p in BOT_GENERIC)
