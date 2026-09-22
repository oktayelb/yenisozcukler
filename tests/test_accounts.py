"""Kayıt, giriş, şifre ve profil uçları."""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.serializers import AuthSerializer

from .helpers import _make_approved_word, _turnstile_fail, _turnstile_ok


class AuthSerializerTests(TestCase):
    """Turnstile burada doğrulanmaz (bkz. accounts/serializers.py):
    tek kullanımlık token view'da harcanır. CAPTCHA reddi
    RegisterViewTests.test_register_captcha_failure ile kapsanıyor."""

    def test_valid_data(self):
        s = AuthSerializer(data={'username': 'alice', 'password': 'pass123', 'token': 'tok'})
        self.assertTrue(s.is_valid(), s.errors)

    def test_password_too_short(self):
        s = AuthSerializer(data={'username': 'alice', 'password': '123', 'token': 'tok'})
        self.assertFalse(s.is_valid())
        self.assertIn('password', s.errors)

    def test_password_too_long(self):
        s = AuthSerializer(data={'username': 'alice', 'password': 'a' * 61, 'token': 'tok'})
        self.assertFalse(s.is_valid())
        self.assertIn('password', s.errors)

    def test_password_exactly_60_chars(self):
        s = AuthSerializer(data={'username': 'alice', 'password': 'a' * 60, 'token': 'tok'})
        self.assertTrue(s.is_valid(), s.errors)

    def test_username_too_long(self):
        s = AuthSerializer(data={'username': 'a' * 31, 'password': 'pass123', 'token': 'tok'})
        self.assertFalse(s.is_valid())
        self.assertIn('username', s.errors)

    def test_username_anonim_blocked(self):
        s = AuthSerializer(data={'username': 'anonim', 'password': 'pass123', 'token': 'tok'})
        self.assertFalse(s.is_valid())

    def test_username_invalid_chars(self):
        s = AuthSerializer(data={'username': 'ali ce!', 'password': 'pass123', 'token': 'tok'})
        self.assertFalse(s.is_valid())
        self.assertIn('username', s.errors)


# ---------------------------------------------------------------------------
# 3. Auth views — register & login
# ---------------------------------------------------------------------------

@override_settings(RATELIMIT_ENABLE=False)
class RegisterViewTests(TestCase):

    @patch('core.http.http_requests.post', side_effect=_turnstile_ok)
    def test_register_creates_user_and_logs_in(self, _mock):
        resp = self.client.post(
            reverse('register'),
            data=json.dumps({'username': 'newuser', 'password': 'Gecerli-Parola-42', 'token': 'tok'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    @patch('core.http.http_requests.post', side_effect=_turnstile_ok)
    def test_register_duplicate_username(self, _mock):
        User.objects.create_user(username='existing', password='pass123')
        resp = self.client.post(
            reverse('register'),
            data=json.dumps({'username': 'existing', 'password': 'pass123', 'token': 'tok'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    @patch('core.http.http_requests.post', side_effect=_turnstile_ok)
    def test_register_duplicate_username_case_insensitive(self, _mock):
        User.objects.create_user(username='Alice', password='pass123')
        resp = self.client.post(
            reverse('register'),
            data=json.dumps({'username': 'alice', 'password': 'pass123', 'token': 'tok'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    @patch('core.http.http_requests.post', side_effect=_turnstile_fail)
    def test_register_captcha_failure(self, _mock):
        resp = self.client.post(
            reverse('register'),
            data=json.dumps({'username': 'user2', 'password': 'pass123', 'token': 'bad'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(User.objects.filter(username='user2').exists())

@override_settings(RATELIMIT_ENABLE=False)
class LoginViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='loginuser', password='correct123')

    @patch('core.http.http_requests.post', side_effect=_turnstile_ok)
    def test_login_success(self, _mock):
        resp = self.client.post(
            reverse('login'),
            data=json.dumps({'username': 'loginuser', 'password': 'correct123', 'token': 'tok'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

    @patch('core.http.http_requests.post', side_effect=_turnstile_ok)
    def test_login_wrong_password(self, _mock):
        resp = self.client.post(
            reverse('login'),
            data=json.dumps({'username': 'loginuser', 'password': 'wrong123', 'token': 'tok'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['success'])

    @patch('core.http.http_requests.post', side_effect=_turnstile_ok)
    def test_login_nonexistent_user(self, _mock):
        resp = self.client.post(
            reverse('login'),
            data=json.dumps({'username': 'nobody', 'password': 'pass123', 'token': 'tok'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

@override_settings(RATELIMIT_ENABLE=False)
class ChangePasswordTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='pwuser', password='correct123')
        self.client.force_login(self.user)

    def _patch(self, current, new):
        return self.client.patch(
            reverse('change_password'),
            data=json.dumps({'current_password': current, 'new_password': new}),
            content_type='application/json',
        )

    def test_successful_change(self):
        resp = self._patch('correct123', 'newpass456')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

    def test_wrong_current_password(self):
        resp = self._patch('wrongpass', 'newpass456')
        self.assertEqual(resp.status_code, 400)

    def test_new_password_too_short(self):
        resp = self._patch('correct123', '12345')
        self.assertEqual(resp.status_code, 400)

    def test_new_password_too_long(self):
        resp = self._patch('correct123', 'a' * 61)
        self.assertEqual(resp.status_code, 400)

    def test_current_password_too_long_rejected(self):
        resp = self._patch('a' * 61, 'newpass456')
        self.assertEqual(resp.status_code, 400)

    def test_session_preserved_after_change(self):
        self._patch('correct123', 'newpass456')
        # update_session_auth_hash keeps the user logged in
        resp = self.client.get(reverse('get_user_profile'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['username'], 'pwuser')

    def test_anonymous_cannot_change_password(self):
        self.client.logout()
        resp = self._patch('correct123', 'newpass456')
        self.assertEqual(resp.status_code, 403)

@override_settings(RATELIMIT_ENABLE=False)
class UserProfileTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='profuser', password='pass123')
        _make_approved_word(user=self.user, word='kelime1', definition='tanim', score=5)

    def test_own_profile_when_authenticated(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('get_user_profile'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['username'], 'profuser')
        self.assertEqual(data['word_count'], 1)
        self.assertEqual(data['total_score'], 5)

    def test_profile_by_username_param(self):
        resp = self.client.get(reverse('get_user_profile'), {'username': 'profuser'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['username'], 'profuser')

    def test_profile_404_for_unknown_user(self):
        resp = self.client.get(reverse('get_user_profile'), {'username': 'nobody'})
        self.assertEqual(resp.status_code, 404)

    def test_unauthenticated_no_username_param_returns_404(self):
        resp = self.client.get(reverse('get_user_profile'))
        self.assertEqual(resp.status_code, 404)
