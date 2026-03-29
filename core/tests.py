import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .middleware import CloudflareSecurityMiddleware, _is_cloudflare_ip
from .models import Category, Comment, CommentVote, Word, WordVote
from .serializers import AuthSerializer, CommentCreateSerializer, WordCreateSerializer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _turnstile_ok(*args, **kwargs):
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


# ---------------------------------------------------------------------------
# 1. Models — display_author property
# ---------------------------------------------------------------------------

class DisplayAuthorTests(TestCase):

    def test_word_display_author_with_user(self):
        user = User.objects.create_user(username='alice', password='pass123')
        word = _make_approved_word(user=user)
        self.assertEqual(word.display_author, 'alice')

    def test_word_display_author_without_user(self):
        word = Word.objects.create(
            word='anonim', definition='tanim', example='örnek.', etymology='test',
            status='approved', author='GuestName',
        )
        self.assertEqual(word.display_author, 'GuestName')

    def test_comment_display_author_with_user(self):
        user = User.objects.create_user(username='bob', password='pass123')
        word = _make_approved_word(user=user)
        comment = Comment.objects.create(word=word, user=user, comment='iyi')
        self.assertEqual(comment.display_author, 'bob')

    def test_comment_display_author_without_user(self):
        word = _make_approved_word()
        comment = Comment.objects.create(word=word, comment='iyi', author='GuestX')
        self.assertEqual(comment.display_author, 'GuestX')


# ---------------------------------------------------------------------------
# 2. Serializers
# ---------------------------------------------------------------------------

class WordCreateSerializerTests(TestCase):

    def setUp(self):
        self.category = Category.objects.create(
            name='Teknoloji', slug='teknoloji',
            description='Tech', is_active=True,
        )

    def _valid_data(self, **overrides):
        data = {
            'word': 'yazılım',
            'definition': 'kodlama sanatı',
            'example': 'yazılım geliştirme zordur.',
            'etymology': 'Türkçe köken',
            'nickname': 'TestKullanici',
        }
        data.update(overrides)
        return data

    def test_valid_submission(self):
        s = WordCreateSerializer(data=self._valid_data())
        self.assertTrue(s.is_valid(), s.errors)

    def test_invalid_char_in_word(self):
        s = WordCreateSerializer(data=self._valid_data(word='ya@zılım'))
        self.assertFalse(s.is_valid())
        self.assertIn('word', s.errors)

    def test_invalid_char_in_definition(self):
        s = WordCreateSerializer(data=self._valid_data(definition='tanım@!'))
        self.assertFalse(s.is_valid())
        self.assertIn('definition', s.errors)

    def test_empty_etymology_rejected(self):
        s = WordCreateSerializer(data=self._valid_data(etymology=''))
        self.assertFalse(s.is_valid())
        self.assertIn('etymology', s.errors)

    def test_nickname_impersonates_real_user(self):
        User.objects.create_user(username='realuser', password='pass123')
        s = WordCreateSerializer(data=self._valid_data(nickname='realuser'))
        self.assertFalse(s.is_valid())
        self.assertIn('nickname', s.errors)

    def test_nickname_impersonation_case_insensitive(self):
        User.objects.create_user(username='RealUser', password='pass123')
        s = WordCreateSerializer(data=self._valid_data(nickname='realuser'))
        self.assertFalse(s.is_valid())

    def test_blank_nickname_becomes_anonim(self):
        s = WordCreateSerializer(data=self._valid_data(nickname=''))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data.get('author'), 'Anonim')

    def test_category_ids_accepted(self):
        s = WordCreateSerializer(data=self._valid_data(category_ids=[self.category.id]))
        self.assertTrue(s.is_valid(), s.errors)

    def test_word_lowercased_turkish(self):
        s = WordCreateSerializer(data=self._valid_data(word='YAZILIM'))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['word'], 'yazılım')


class CommentCreateSerializerTests(TestCase):

    def test_valid_comment(self):
        s = CommentCreateSerializer(data={'word_id': 1, 'comment': 'güzel yorum'})
        self.assertTrue(s.is_valid(), s.errors)

    def test_empty_comment_rejected(self):
        s = CommentCreateSerializer(data={'word_id': 1, 'comment': '   '})
        self.assertFalse(s.is_valid())

    def test_comment_too_long(self):
        s = CommentCreateSerializer(data={'word_id': 1, 'comment': 'a' * 201})
        self.assertFalse(s.is_valid())

    def test_comment_exactly_200_chars(self):
        s = CommentCreateSerializer(data={'word_id': 1, 'comment': 'a' * 200})
        self.assertTrue(s.is_valid(), s.errors)


@override_settings(RATELIMIT_ENABLE=False)
class AuthSerializerTests(TestCase):

    @patch('core.serializers.requests.post', side_effect=_turnstile_ok)
    def test_valid_data(self, _mock):
        s = AuthSerializer(data={'username': 'alice', 'password': 'pass123', 'token': 'tok'})
        self.assertTrue(s.is_valid(), s.errors)

    @patch('core.serializers.requests.post', side_effect=_turnstile_ok)
    def test_password_too_short(self, _mock):
        s = AuthSerializer(data={'username': 'alice', 'password': '123', 'token': 'tok'})
        self.assertFalse(s.is_valid())
        self.assertIn('password', s.errors)

    @patch('core.serializers.requests.post', side_effect=_turnstile_ok)
    def test_password_too_long(self, _mock):
        s = AuthSerializer(data={'username': 'alice', 'password': 'a' * 61, 'token': 'tok'})
        self.assertFalse(s.is_valid())
        self.assertIn('password', s.errors)

    @patch('core.serializers.requests.post', side_effect=_turnstile_ok)
    def test_password_exactly_60_chars(self, _mock):
        s = AuthSerializer(data={'username': 'alice', 'password': 'a' * 60, 'token': 'tok'})
        self.assertTrue(s.is_valid(), s.errors)

    @patch('core.serializers.requests.post', side_effect=_turnstile_ok)
    def test_username_too_long(self, _mock):
        s = AuthSerializer(data={'username': 'a' * 31, 'password': 'pass123', 'token': 'tok'})
        self.assertFalse(s.is_valid())
        self.assertIn('username', s.errors)

    @patch('core.serializers.requests.post', side_effect=_turnstile_ok)
    def test_username_anonim_blocked(self, _mock):
        s = AuthSerializer(data={'username': 'anonim', 'password': 'pass123', 'token': 'tok'})
        self.assertFalse(s.is_valid())

    @patch('core.serializers.requests.post', side_effect=_turnstile_ok)
    def test_username_invalid_chars(self, _mock):
        s = AuthSerializer(data={'username': 'ali ce!', 'password': 'pass123', 'token': 'tok'})
        self.assertFalse(s.is_valid())
        self.assertIn('username', s.errors)

    @patch('core.serializers.requests.post', side_effect=_turnstile_fail)
    def test_turnstile_fail_rejected(self, _mock):
        s = AuthSerializer(data={'username': 'alice', 'password': 'pass123', 'token': 'bad'})
        self.assertFalse(s.is_valid())


# ---------------------------------------------------------------------------
# 3. Auth views — register & login
# ---------------------------------------------------------------------------

@override_settings(RATELIMIT_ENABLE=False)
class RegisterViewTests(TestCase):

    @patch('core.serializers.requests.post', side_effect=_turnstile_ok)
    def test_register_creates_user_and_logs_in(self, _mock):
        resp = self.client.post(
            reverse('register'),
            data=json.dumps({'username': 'newuser', 'password': 'pass123', 'token': 'tok'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    @patch('core.serializers.requests.post', side_effect=_turnstile_ok)
    def test_register_duplicate_username(self, _mock):
        User.objects.create_user(username='existing', password='pass123')
        resp = self.client.post(
            reverse('register'),
            data=json.dumps({'username': 'existing', 'password': 'pass123', 'token': 'tok'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    @patch('core.serializers.requests.post', side_effect=_turnstile_fail)
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

    @patch('core.serializers.requests.post', side_effect=_turnstile_ok)
    def test_login_success(self, _mock):
        resp = self.client.post(
            reverse('login'),
            data=json.dumps({'username': 'loginuser', 'password': 'correct123', 'token': 'tok'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

    @patch('core.serializers.requests.post', side_effect=_turnstile_ok)
    def test_login_wrong_password(self, _mock):
        resp = self.client.post(
            reverse('login'),
            data=json.dumps({'username': 'loginuser', 'password': 'wrong123', 'token': 'tok'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['success'])

    @patch('core.serializers.requests.post', side_effect=_turnstile_ok)
    def test_login_nonexistent_user(self, _mock):
        resp = self.client.post(
            reverse('login'),
            data=json.dumps({'username': 'nobody', 'password': 'pass123', 'token': 'tok'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# 4. Voting
# ---------------------------------------------------------------------------

@override_settings(RATELIMIT_ENABLE=False)
class VoteTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='voter', password='pass123')
        self.word = _make_approved_word(user=self.user)

    def _vote(self, action, word_id=None):
        word_id = word_id or self.word.id
        return self.client.post(
            reverse('vote', args=['word', word_id]),
            data=json.dumps({'action': action}),
            content_type='application/json',
        )

    def test_anonymous_cannot_vote(self):
        resp = self._vote('like')
        self.assertEqual(resp.status_code, 403)

    def test_like_increases_score(self):
        self.client.force_login(self.user)
        resp = self._vote('like')
        self.assertEqual(resp.status_code, 200)
        self.word.refresh_from_db()
        self.assertEqual(self.word.score, 1)

    def test_dislike_decreases_score(self):
        self.client.force_login(self.user)
        self._vote('like')
        self._vote('dislike')  # toggle from like to dislike: +1 → -1
        self.word.refresh_from_db()
        self.assertEqual(self.word.score, -1)

    def test_like_twice_toggles_off(self):
        self.client.force_login(self.user)
        self._vote('like')
        self._vote('like')  # cancel vote
        self.word.refresh_from_db()
        self.assertEqual(self.word.score, 0)

    def test_cannot_vote_pending_word(self):
        self.client.force_login(self.user)
        pending = _make_pending_word(user=self.user)
        resp = self._vote('like', word_id=pending.id)
        self.assertEqual(resp.status_code, 404)

    def test_invalid_action_rejected(self):
        self.client.force_login(self.user)
        resp = self._vote('explode')
        self.assertEqual(resp.status_code, 400)

    def test_comment_vote(self):
        self.client.force_login(self.user)
        comment = Comment.objects.create(word=self.word, user=self.user, comment='yorum')
        resp = self.client.post(
            reverse('vote', args=['comment', comment.id]),
            data=json.dumps({'action': 'like'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        comment.refresh_from_db()
        self.assertEqual(comment.score, 1)

    def test_invalid_entity_type(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse('vote', args=['planet', self.word.id]),
            data=json.dumps({'action': 'like'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# 5. add_word and add_comment
# ---------------------------------------------------------------------------

@override_settings(RATELIMIT_ENABLE=False)
class AddWordTests(TestCase):

    def _valid_payload(self, **overrides):
        data = {
            'word': 'yenikelime',
            'definition': 'yeni bir kelime',
            'example': 'bu yeni bir kelimedir.',
            'etymology': 'Türkçe',
        }
        data.update(overrides)
        return data

    def test_anonymous_can_submit_word(self):
        resp = self.client.post(
            reverse('add_word'),
            data=json.dumps(self._valid_payload()),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(Word.objects.filter(word='yenikelime').count(), 1)

    def test_submitted_word_is_pending(self):
        self.client.post(
            reverse('add_word'),
            data=json.dumps(self._valid_payload()),
            content_type='application/json',
        )
        word = Word.objects.get(word='yenikelime')
        self.assertEqual(word.status, 'pending')

    def test_authenticated_word_linked_to_user(self):
        user = User.objects.create_user(username='writer', password='pass123')
        self.client.force_login(user)
        self.client.post(
            reverse('add_word'),
            data=json.dumps(self._valid_payload()),
            content_type='application/json',
        )
        word = Word.objects.get(word='yenikelime')
        self.assertEqual(word.user, user)

    def test_invalid_word_rejected(self):
        resp = self.client.post(
            reverse('add_word'),
            data=json.dumps(self._valid_payload(word='bad@word!')),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)


@override_settings(RATELIMIT_ENABLE=False)
class AddCommentTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='commenter', password='pass123')
        self.word = _make_approved_word(user=self.user)

    def test_anonymous_cannot_comment(self):
        resp = self.client.post(
            reverse('add_comment'),
            data=json.dumps({'word_id': self.word.id, 'comment': 'güzel'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_authenticated_can_comment(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse('add_comment'),
            data=json.dumps({'word_id': self.word.id, 'comment': 'güzel'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)

    def test_cannot_comment_pending_word(self):
        self.client.force_login(self.user)
        pending = _make_pending_word(user=self.user)
        resp = self.client.post(
            reverse('add_comment'),
            data=json.dumps({'word_id': pending.id, 'comment': 'güzel'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_empty_comment_rejected(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse('add_comment'),
            data=json.dumps({'word_id': self.word.id, 'comment': ''}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# 6. add_example
# ---------------------------------------------------------------------------

@override_settings(RATELIMIT_ENABLE=False)
class AddExampleTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass123')
        self.other = User.objects.create_user(username='other', password='pass123')
        self.word = Word.objects.create(
            word='örnekyok',
            definition='tanim',
            example='',
            etymology='test',
            status='approved',
            user=self.owner,
        )

    def test_owner_can_add_example(self):
        self.client.force_login(self.owner)
        resp = self.client.patch(
            reverse('add_example'),
            data=json.dumps({'word_id': self.word.id, 'example': 'yeni örnek cümlesi.'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.word.refresh_from_db()
        self.assertEqual(self.word.example, 'yeni örnek cümlesi.')

    def test_non_owner_cannot_add_example(self):
        self.client.force_login(self.other)
        resp = self.client.patch(
            reverse('add_example'),
            data=json.dumps({'word_id': self.word.id, 'example': 'hacker örnek.'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_cannot_overwrite_existing_example(self):
        self.word.example = 'zaten var.'
        self.word.save()
        self.client.force_login(self.owner)
        resp = self.client.patch(
            reverse('add_example'),
            data=json.dumps({'word_id': self.word.id, 'example': 'yeni örnek.'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_anonymous_cannot_add_example(self):
        resp = self.client.patch(
            reverse('add_example'),
            data=json.dumps({'word_id': self.word.id, 'example': 'yeni örnek.'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# 7. change_password
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 8. get_words — search, pagination, sort, invalid params
# ---------------------------------------------------------------------------

@override_settings(RATELIMIT_ENABLE=False)
class GetWordsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='worduser', password='pass123')
        _make_approved_word(user=self.user, word='araba', definition='taşıt')
        _make_approved_word(user=self.user, word='bilgisayar', definition='elektronik cihaz', score=10)
        _make_pending_word(user=self.user)

    def test_only_approved_words_returned(self):
        resp = self.client.get(reverse('get_words'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['words']), 2)

    def test_search_by_word(self):
        resp = self.client.get(reverse('get_words'), {'search': 'araba'})
        words = resp.json()['words']
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0]['word'], 'araba')

    def test_search_by_definition(self):
        resp = self.client.get(reverse('get_words'), {'search': 'taşıt'})
        self.assertEqual(len(resp.json()['words']), 1)

    def test_search_long_query_does_not_crash(self):
        # Server caps at 40 chars — must not raise
        resp = self.client.get(reverse('get_words'), {'search': 'a' * 60})
        self.assertEqual(resp.status_code, 200)

    def test_invalid_limit_falls_back_to_default(self):
        resp = self.client.get(reverse('get_words'), {'limit': 'abc'})
        self.assertEqual(resp.status_code, 200)

    def test_limit_capped_at_50(self):
        resp = self.client.get(reverse('get_words'), {'limit': '999'})
        self.assertEqual(resp.status_code, 200)

    def test_sort_score_desc(self):
        resp = self.client.get(reverse('get_words'), {'sort': 'score_desc'})
        scores = [w['score'] for w in resp.json()['words']]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_sort_date_asc(self):
        resp = self.client.get(reverse('get_words'), {'sort': 'date_asc'})
        self.assertEqual(resp.status_code, 200)

    def test_invalid_page_returns_empty(self):
        resp = self.client.get(reverse('get_words'), {'page': '9999'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['words'], [])


# ---------------------------------------------------------------------------
# 9. get_user_profile
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 10. get_my_words
# ---------------------------------------------------------------------------

@override_settings(RATELIMIT_ENABLE=False)
class GetMyWordsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='myuser', password='pass123')
        _make_approved_word(user=self.user, word='kelime1', definition='tanim')
        _make_pending_word(user=self.user)

    def test_own_words_excludes_pending(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('get_my_words'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total_count'], 1)

    def test_anonymous_without_username_param_is_401(self):
        resp = self.client.get(reverse('get_my_words'))
        self.assertEqual(resp.status_code, 401)

    def test_public_words_by_username_param(self):
        resp = self.client.get(reverse('get_my_words'), {'username': 'myuser'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total_count'], 1)


# ---------------------------------------------------------------------------
# 11. Middleware — _is_cloudflare_ip unit tests
# ---------------------------------------------------------------------------

class CloudflareIPTests(TestCase):

    def test_known_cloudflare_ipv4_accepted(self):
        # 104.16.0.1 is inside 104.16.0.0/13
        self.assertTrue(_is_cloudflare_ip('104.16.0.1'))

    def test_known_cloudflare_ipv4_another_range(self):
        # 173.245.48.1 is inside 173.245.48.0/20
        self.assertTrue(_is_cloudflare_ip('173.245.48.1'))

    def test_non_cloudflare_ipv4_rejected(self):
        self.assertFalse(_is_cloudflare_ip('1.2.3.4'))

    def test_known_cloudflare_ipv6_accepted(self):
        # 2606:4700::1 is inside 2606:4700::/32
        self.assertTrue(_is_cloudflare_ip('2606:4700::1'))

    def test_non_cloudflare_ipv6_rejected(self):
        self.assertFalse(_is_cloudflare_ip('2001:db8::1'))

    def test_invalid_ip_string_returns_false(self):
        self.assertFalse(_is_cloudflare_ip('not-an-ip'))

    def test_loopback_not_cloudflare(self):
        self.assertFalse(_is_cloudflare_ip('127.0.0.1'))


class CloudflareMiddlewareTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

        def dummy_view(request):
            from django.http import HttpResponse
            return HttpResponse('ok')

        self.middleware = CloudflareSecurityMiddleware(dummy_view)

    @override_settings(DEBUG=False)
    def test_production_blocks_request_without_cf_header(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 403)

    @override_settings(DEBUG=False)
    def test_production_blocks_non_cloudflare_remote_addr(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        request.META['HTTP_CF_CONNECTING_IP'] = '8.8.8.8'
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 403)

    @override_settings(DEBUG=False)
    def test_production_allows_real_cloudflare_ip(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '104.16.0.1'
        request.META['HTTP_CF_CONNECTING_IP'] = '8.8.8.8'
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    @override_settings(DEBUG=True)
    def test_debug_mode_allows_any_ip(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    @override_settings(DEBUG=False)
    def test_localhost_always_allowed_in_production(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    @override_settings(DEBUG=False)
    def test_ipv6_localhost_always_allowed(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '::1'
        resp = self.middleware(request)
        self.assertEqual(resp.status_code, 200)

    def test_security_headers_added(self):
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        resp = self.middleware(request)
        self.assertIn('Permissions-Policy', resp)
