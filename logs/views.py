from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from core.http import get_client_ip, verify_turnstile

from . import ban_pass
from .logger import log_activity


@csrf_exempt
@require_POST
@ratelimit(key='ip', rate='10/m', method='POST', block=False)
def ban_pass_view(request):
    next_url = ban_pass.safe_next_url(request, request.POST.get('next'))

    if getattr(request, 'limited', False):
        log_activity(request, 'ban_pass_failed', detail='Çok fazla deneme')
        return ban_pass.challenge_page(
            next_url, 'Çok fazla deneme. Biraz bekleyip tekrar deneyin.', status=429,
        )

    if not verify_turnstile(request.POST.get('cf-turnstile-response')):
        log_activity(request, 'ban_pass_failed', detail='Turnstile doğrulanamadı')
        return ban_pass.challenge_page(next_url, 'Doğrulama başarısız oldu, lütfen tekrar deneyin.')

    log_activity(request, 'ban_pass', detail='Turnstile doğrulandı')
    response = redirect(next_url)
    ip = get_client_ip(request)
    if ip is not None:
        ban_pass.grant_pass(response, ip)
    return response
