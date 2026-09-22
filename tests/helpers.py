"""Testler arası paylaşılan yardımcılar."""

from unittest.mock import MagicMock

from words.models import Word


def _turnstile_ok(*args, **kwargs):
    """`core.http.http_requests.post` yerine geçer: CAPTCHA geçti."""
    mock = MagicMock()
    mock.json.return_value = {'success': True}
    return mock


def _turnstile_fail(*args, **kwargs):
    mock = MagicMock()
    mock.json.return_value = {'success': False}
    return mock


def _make_approved_word(user=None, word='test', definition='tanim', score=0):
    return Word.objects.create(
        word=word,
        definition=definition,
        example='örnek cümle.',
        etymology='test',
        status='approved',
        user=user,
        author=user.username if user else 'Anonim',
        score=score,
    )


def _make_pending_word(user=None):
    return Word.objects.create(
        word='bekliyor',
        definition='tanim',
        example='örnek cümle.',
        etymology='test',
        status='pending',
        user=user,
        author=user.username if user else 'Anonim',
    )
