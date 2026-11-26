from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils.http import url_has_allowed_host_and_scheme

PATH = '/api/ban-pass'
COOKIE_NAME = 'ban_pass'
COOKIE_SALT = 'logs.ban_pass'
COOKIE_MAX_AGE = 7 * 24 * 60 * 60

API_ERROR = 'Bu ağdan erişim engellendi. Sayfayı yenileyip doğrulamayı tamamlayın.'


def has_pass(request, ip):
    value = request.get_signed_cookie(
        COOKIE_NAME, default=None, salt=COOKIE_SALT, max_age=COOKIE_MAX_AGE,
    )
    return value is not None and value == ip


def grant_pass(response, ip):
    response.set_signed_cookie(
        COOKIE_NAME, ip, salt=COOKIE_SALT, max_age=COOKIE_MAX_AGE,
        secure=settings.SESSION_COOKIE_SECURE, httponly=True, samesite='Lax',
    )


def safe_next_url(request, url):
    if not url or url.startswith('/api/'):
        return '/'
    is_safe = url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    )
    if not is_safe:
        return '/'
    return url


def challenge_page(next_url, error='', status=403):
    html = render_to_string('banned.html', {
        'action': PATH,
        'next': next_url,
        'error': error,
    })
    response = HttpResponse(html, status=status)
    response['Cache-Control'] = 'no-store'
    return response


def blocked_response(request):
    if request.path.startswith('/api/'):
        return JsonResponse({'success': False, 'error': API_ERROR}, status=403)
    if request.method == 'GET':
        next_url = safe_next_url(request, request.get_full_path())
    else:
        next_url = '/'
    return challenge_page(next_url)
