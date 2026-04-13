# core/views.py
import logging
import requests as http_requests

from django.conf import settings
from decouple import config
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication

from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse, HttpResponseNotFound
from django_ratelimit.decorators import ratelimit
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.db.models import Count, F, Sum, Q
from django.db import transaction, DatabaseError, OperationalError, IntegrityError

from .models import Word, Comment, WordVote, CommentVote, Category, Notification
from .serializers import (
    WordSerializer, CommentSerializer,
    WordCreateSerializer, CommentCreateSerializer,
    AuthSerializer, ChangeUsernameSerializer,
    WordAddExampleSerializer, CategorySerializer,
    NotificationSerializer
)

logger = logging.getLogger(__name__)

# --- YARDIMCI FONKSİYONLAR ---

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

def get_client_ip(request):
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf_ip:
        return cf_ip
        
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()

    return request.META.get('REMOTE_ADDR')

def universal_rate_key(group, request):
    if hasattr(request, 'user') and request.user.is_authenticated:
        return f"user_{request.user.id}"
    return f"ip_{get_client_ip(request)}"

def login_username_key(group, request):
    """Rate-limit key that reads username from JSON body (not request.POST)."""
    import json
    username = ''
    try:
        body = json.loads(request.body)
        username = body.get('username', '').strip().lower()
    except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
        username = request.POST.get('username', '').strip().lower()
    return username or get_client_ip(request)

# --- ROBOTS.TXT ---

_ROBOTS_TXT = (
    "User-agent: *\n"
    "Allow: /\n"
    "Disallow: /api/\n"
    "Disallow: /admin/\n"
)

def robots_txt(request):
    return HttpResponse(_ROBOTS_TXT, content_type='text/plain')

# --- BOT DETECTION ---

BOT_SPECIFIC = [
    'googlebot', 'bingbot', 'yandexbot', 'duckduckbot', 'baiduspider',
    'slurp', 'facebookexternalhit', 'linkedinbot',
    'whatsapp', 'telegrambot', 'discordbot', 'applebot',
]
BOT_GENERIC = ['bot', 'crawler', 'spider', 'scraper', 'preview']

def _is_bot(ua):
    ua = (ua or '').lower()
    return any(p in ua for p in BOT_SPECIFIC) or any(p in ua for p in BOT_GENERIC)

# --- DYNAMIC RENDERING VIEWS ---

@permission_classes([])
def index_view(request):
    if _is_bot(request.META.get('HTTP_USER_AGENT')):
        words = Word.objects.filter(status='approved').select_related('user').order_by('-timestamp')[:50]
        response = render(request, 'bot_index.html', {'words': words})
    else:
        response = render(request, 'index.html')
    
    response['Vary'] = 'User-Agent'
    return response

@permission_classes([])
def category_view(request, slug):
    if _is_bot(request.META.get('HTTP_USER_AGENT')):
        category = get_object_or_404(Category, slug=slug)
        words = Word.objects.filter(status='approved', categories=category).select_related('user').order_by('-timestamp')[:50]
        response = render(request, 'bot_category.html', {'category': category, 'words': words})
    else:
        response = render(request, 'index.html')
        
    response['Vary'] = 'User-Agent'
    return response

@permission_classes([])
def word_detail(request, word_slug):
    if _is_bot(request.META.get('HTTP_USER_AGENT')):
        word = get_object_or_404(
            Word.objects.select_related('user').prefetch_related('categories'),
            slug=word_slug,
            status='approved'
        )
        response = render(request, 'word_detail.html', {'word': word})
    else:
        response = render(request, 'index.html')

    response['Vary'] = 'User-Agent'
    return response

@permission_classes([])
def spa_catchall(request, *args, **kwargs):
    if _is_bot(request.META.get('HTTP_USER_AGENT')):
        return HttpResponseNotFound()
    return render(request, 'index.html')


# --- OKUMA (READ) ENDPOINTLERİ ---

@ratelimit(key='ip', rate='60/m', method='GET', block=False)
@api_view(['GET'])
@permission_classes([])
def get_categories(request):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    cache_key = 'all_active_categories'
    categories_data = cache.get(cache_key)
    
    if not categories_data:
        categories = Category.objects.filter(is_active=True)
        serializer = CategorySerializer(categories, many=True)
        categories_data = serializer.data
        cache.set(cache_key, categories_data, 60 * 60) 

    return Response({'success': True, 'categories': categories_data})

@ratelimit(key='ip', rate='120/m', method='GET', block=False)
@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([])
def get_words(request):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    page_number = request.GET.get('page', 1)
    try:
        limit = int(request.GET.get('limit', 20))
    except (ValueError, TypeError):
        limit = 20
    limit = min(limit, 50)
    tag_slug = request.GET.get('tag')
    sort = request.GET.get('sort', 'date_desc')
    search_query = request.GET.get('search', '').strip()[:40]

    words_queryset = Word.objects.filter(status='approved')\
        .annotate(comment_count=Count('comments'))\
        .select_related('user')\
        .prefetch_related('categories')\
        .only('id', 'word', 'definition', 'example', 'etymology', 'author', 'timestamp', 'score', 'user__username')

    if sort == 'date_asc':
        words_queryset = words_queryset.order_by('timestamp')
    elif sort == 'score_desc':
        words_queryset = words_queryset.order_by('-score', '-timestamp')
    elif sort == 'score_asc':
        words_queryset = words_queryset.order_by('score', '-timestamp')
    else:
        words_queryset = words_queryset.order_by('-timestamp')
    
    if tag_slug:
        words_queryset = words_queryset.filter(categories__slug=tag_slug)

    if search_query:
        words_queryset = words_queryset.filter(
            Q(word__icontains=search_query) | 
            Q(definition__icontains=search_query)
        )

    if not tag_slug and not search_query:
        cache_key = 'total_approved_words_count_all'
        total_count = cache.get(cache_key)
        if total_count is None:
            total_count = words_queryset.count()
            cache.set(cache_key, total_count, 60 * 5)
    else:
        total_count = words_queryset.count()

    paginator = Paginator(words_queryset, limit)
    try:
        words_page = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        words_page = []

    user_votes = {}
    
    try:
        if words_page and request.user.is_authenticated:
            page_word_ids = [w.id for w in words_page]
            votes = WordVote.objects.filter(
                user=request.user, 
                word_id__in=page_word_ids
            ).values('word', 'value')
            
            for v in votes:
                user_votes[v['word']] = v['value']
                
    except (DatabaseError, OperationalError):
        pass

    serializer = WordSerializer(words_page, many=True, context={'user_votes': user_votes})

    return Response({
        'status': 'full',
        'words': serializer.data,
        'total_count': total_count
    })

@ratelimit(key='ip', rate='120/m', method='GET', block=False)
@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([])
def get_comments(request, word_id):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    page = request.GET.get('page', 1)
    try:
        limit = int(request.GET.get('limit', 10))
    except (ValueError, TypeError):
        limit = 10
    limit = min(limit, 20)

    word = get_object_or_404(Word, id=word_id, status='approved')
    comments_qs = Comment.objects.filter(word=word).select_related('user').order_by('timestamp')
    paginator = Paginator(comments_qs, limit)

    try:
        comments_page = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        comments_page = []

    user_votes = {} 

    try:
        if comments_page and request.user.is_authenticated:
            page_comment_ids = [c.id for c in comments_page]
            votes = CommentVote.objects.filter(
                user=request.user,
                comment_id__in=page_comment_ids
            ).values('comment', 'value')

            for v in votes:
                user_votes[v['comment']] = v['value']
    except (DatabaseError, OperationalError):
        pass

    serializer = CommentSerializer(comments_page, many=True, context={'user_votes': user_votes})
    
    return Response({
        'success': True, 
        'comments': serializer.data,
        'has_next': comments_page.has_next() if hasattr(comments_page, 'has_next') else False
    })


@ratelimit(key='ip', rate='120/m', method='GET', block=False)
@api_view(['GET'])
@permission_classes([])
def get_word(request, word_id):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    word = get_object_or_404(
        Word.objects.filter(status='approved')
            .annotate(comment_count=Count('comments'))
            .select_related('user')
            .prefetch_related('categories'),
        id=word_id
    )

    user_votes = {}
    if request.user.is_authenticated:
        vote = WordVote.objects.filter(user=request.user, word=word).values('value').first()
        if vote:
            user_votes[word.id] = vote['value']

    serializer = WordSerializer(word, context={'user_votes': user_votes})
    return Response({'success': True, 'word': serializer.data})


@ratelimit(key='ip', rate='120/m', method='GET', block=False)
@api_view(['GET'])
@permission_classes([])
def get_word_by_slug(request, word_slug):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    cache_key = f'word_slug_{word_slug}'
    word = cache.get(cache_key)
    if word is None:
        word = get_object_or_404(
            Word.objects.filter(status='approved')
                .annotate(comment_count=Count('comments'))
                .select_related('user')
                .prefetch_related('categories'),
            slug=word_slug
        )
        cache.set(cache_key, word, 60 * 60)

    user_votes = {}
    if request.user.is_authenticated:
        vote = WordVote.objects.filter(user=request.user, word=word).values('value').first()
        if vote:
            user_votes[word.id] = vote['value']

    serializer = WordSerializer(word, context={'user_votes': user_votes})
    return Response({'success': True, 'word': serializer.data})


# --- YAZMA (WRITE) ENDPOINTLERİ ---

@ratelimit(key='ip', rate='100/m', method='POST', block=False)
@ratelimit(key=universal_rate_key, rate='15/m', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
@transaction.atomic 
def vote(request, entity_type, entity_id):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    client_ip = get_client_ip(request)
    user = request.user
    
    action = request.data.get('action') 
    if action not in ['like', 'dislike']:
        return Response({'error': 'Geçersiz işlem.'}, status=400)

    vote_val = 1 if action == 'like' else -1

    if entity_type == 'word':
        ModelClass = Word
        VoteClass = WordVote
        lookup_field = 'word'
    elif entity_type == 'comment':
        ModelClass = Comment
        VoteClass = CommentVote
        lookup_field = 'comment'
    else:
        return Response({'error': 'Geçersiz tip.'}, status=404)

    obj = get_object_or_404(ModelClass.objects.select_for_update(), id=entity_id)
    
    if entity_type == 'word' and obj.status != 'approved':
        return Response({'error': 'Geçersiz içerik.'}, status=404)

    existing_vote = VoteClass.objects.filter(user=user, **{lookup_field: obj}).first()
    response_action = 'none'

    if existing_vote:
        if existing_vote.value == vote_val:
            existing_vote.delete()
            obj.score = F('score') - vote_val
            response_action = 'none'
        else:
            existing_vote.value = vote_val
            existing_vote.save(update_fields=['value'])
            obj.score = F('score') + (vote_val * 2)
            response_action = 'liked' if vote_val == 1 else 'disliked'
    else:
        try:
            new_vote = VoteClass(
                value=vote_val,
                ip_address=client_ip,
                user=user,
                **{lookup_field: obj}
            )
            new_vote.save()
        except IntegrityError:
            return Response({'error': 'Oy zaten kaydedildi.'}, status=409)
        obj.score = F('score') + vote_val
        response_action = 'liked' if vote_val == 1 else 'disliked'

    obj.save(update_fields=['score'])
    obj.refresh_from_db()

    owner = obj.user if hasattr(obj, 'user') else None
    if owner and owner != user:
        prefix = 'word' if entity_type == 'word' else 'comment'
        like_type = f'{prefix}_like'
        dislike_type = f'{prefix}_dislike'
        current_type = like_type if vote_val == 1 else dislike_type
        opposite_type = dislike_type if vote_val == 1 else like_type

        # This dictionary is critical to preventing the lookup_kwargs error.
        lookup_kwargs = {'word': obj} if entity_type == 'word' else {'comment': obj}

        if response_action == 'none':
            # SOFT DELETE: Instead of .delete(), we deactivate it.
            updated = Notification.objects.filter(
                recipient=owner, actor=user, notification_type=current_type, **lookup_kwargs
            ).update(is_active=False)
            
            if updated:
                cache.delete(f'notif_unread_{owner.id}')
        else:
            # Deactivate the opposite vote type (e.g. they switched from dislike to like)
            Notification.objects.filter(
                recipient=owner, actor=user, notification_type=opposite_type, **lookup_kwargs
            ).update(is_active=False)
            
            # This defaults dictionary is also required for get_or_create
            defaults = {'comment': None} if entity_type == 'word' else {'word': obj.word}
            defaults['is_active'] = True
            
            # Fetch or create the notification. 
            notif, created = Notification.objects.get_or_create(
                recipient=owner, actor=user, notification_type=current_type, 
                **lookup_kwargs, defaults=defaults
            )
            
            # REVIVE: If it existed but was deactivated, turn it back on.
            if not created and not notif.is_active:
                notif.is_active = True
                notif.is_read = False  # Mark unread so they see it again
                notif.save(update_fields=['is_active', 'is_read'])
                cache.delete(f'notif_unread_{owner.id}')
            elif created:
                cache.delete(f'notif_unread_{owner.id}')

    return Response({
        'success': True,
        'new_score': obj.score,
        'user_action': response_action
    })

@ratelimit(key='ip', rate='30/m', method='POST', block=False)
@ratelimit(key=universal_rate_key, rate='5/m', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([])
@transaction.atomic
def add_word(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)
    
    captcha_token = request.data.get('cf_turnstile_response')
    if not verify_turnstile(captcha_token):
        return Response({'success': False, 'error': 'Lütfen robot olmadığınızı doğrulayın.'}, status=400)
    
    serializer = WordCreateSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        client_ip = get_client_ip(request)
        save_kwargs = {'status': 'pending', 'ip_address': client_ip}
        
        if request.user.is_authenticated:
            save_kwargs['user'] = request.user
        else:
            save_kwargs['author'] = 'Anonim'
        
        word = serializer.save(**save_kwargs)
        
        if request.user.is_authenticated:
            WordVote.objects.create(
                word=word,
                user=request.user,
                value=1,
                ip_address=client_ip
            )
            word.score = 1
            word.save(update_fields=['score'])

        cache.delete('total_approved_words_count_all')
        
        return Response({'success': True})
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)

@ratelimit(key='ip', rate='20/m', method='PATCH', block=False)
@ratelimit(key=universal_rate_key, rate='5/m', method='PATCH', block=False)
@api_view(['PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
@transaction.atomic
def add_example(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    serializer = WordAddExampleSerializer(data=request.data)
    
    if serializer.is_valid():
        word_id = serializer.validated_data['word_id']
        new_example = serializer.validated_data['example']
        word = get_object_or_404(Word.objects.select_for_update(), id=word_id)

        if word.user != request.user:
            return Response({'success': False, 'error': 'Bu kelimeyi düzenleme yetkiniz yok.'}, status=403)

        if word.example and word.example.strip():
            return Response({'success': False, 'error': 'Bu kelimenin zaten bir örnek cümlesi var.'}, status=400)

        word.example = new_example
        word.save(update_fields=['example'])
        return Response({'success': True, 'message': 'Örnek cümle başarıyla eklendi.'})

    first_error = next(iter(serializer.errors.values()))[0]
    return Response({'success': False, 'error': first_error}, status=400)

@ratelimit(key='ip', rate='50/m', method='POST', block=False)
@ratelimit(key=universal_rate_key, rate='10/m', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
@transaction.atomic
def add_comment(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    serializer = CommentCreateSerializer(data=request.data)
    
    if serializer.is_valid():
        word = get_object_or_404(Word, id=serializer.validated_data['word_id'], status='approved')
        client_ip = get_client_ip(request)

        new_comment = Comment.objects.create(
            word=word,
            user=request.user,
            author=request.user.username,
            comment=serializer.validated_data['comment'],
            score=0
        )

        CommentVote.objects.create(
            comment=new_comment,
            user=request.user,
            value=1,
            ip_address=client_ip
        )
        Comment.objects.filter(pk=new_comment.pk).update(score=F('score') + 1)
        new_comment.score = 1

        if word.user and word.user != request.user:
            Notification.objects.create(
                recipient=word.user,
                actor=request.user,
                notification_type='new_comment',
                word=word,
                comment=new_comment,
            )
            cache.delete(f'notif_unread_{word.user.id}')

        return Response({'success': True, 'comment': CommentSerializer(new_comment).data}, status=201)
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)
    
## Profil İşlemleri

@ratelimit(key='ip', rate='20/m', method='POST', block=False)
@ratelimit(key=login_username_key, rate='5/10m', method='POST', block=False)
@api_view(['POST'])
@permission_classes([])
def login_view(request):
    if getattr(request, 'limited', False):
         return Response({'success': False, 'error': 'Çok fazla giriş denemesi. Lütfen bekleyin.'}, status=429)

    captcha_token = request.data.get('token')
    if not verify_turnstile(captcha_token):
        return Response({'success': False, 'error': 'Lütfen robot olmadığınızı doğrulayın.'}, status=400)

    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')

    if not username or not password:
        return Response({'success': False, 'error': 'Geçersiz veri.'}, status=400)

    try:
        db_user = User.objects.get(username__iexact=username)
        canonical_username = db_user.username
    except User.DoesNotExist:
        canonical_username = username
    except User.MultipleObjectsReturned:
        canonical_username = username

    user = authenticate(request, username=canonical_username, password=password)

    if user is None:
        return Response({'success': False, 'error': 'Bu kullanıcı adı veya şifre hatalı.'}, status=400)
    
    login(request, user)    

    return Response({'success': True, 'username': user.username, 'message': 'Giriş başarılı.'})

@ratelimit(key='ip', rate='10/h', method='POST', block=False)
@ratelimit(key=universal_rate_key, rate='2/h', method='POST', block=False)
@api_view(['POST'])
@permission_classes([])
def register_view(request):
    if getattr(request, 'limited', False):
         return Response({'success': False, 'error': 'Çok fazla kayıt denemesi. Lütfen daha sonra tekrar deneyin.'}, status=429)

    captcha_token = request.data.get('token')
    if not verify_turnstile(captcha_token):
        return Response({'success': False, 'error': 'Lütfen robot olmadığınızı doğrulayın.'}, status=400)

    serializer = AuthSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data['username'].lower()
        password = serializer.validated_data['password']

        if User.objects.filter(username=username).exists():
            return Response({'success': False, 'error': 'Bu kullanıcı adı zaten alınmış.'}, status=400)

        try:
            validate_password(password)
        except DjangoValidationError as e:
            return Response({'success': False, 'error': e.messages[0]}, status=400)

        try:
            with transaction.atomic():
                user = User.objects.create_user(username=username, password=password)
                login(request, user)
                return Response({'success': True, 'username': user.username, 'message': 'Kayıt başarılı.'}, status=201)
        except IntegrityError:
            return Response({'success': False, 'error': 'Bu kullanıcı adı zaten alınmış.'}, status=400)
        except Exception as e:
            logger.error('register_view failed for username=%s: %s', username, e, exc_info=True)
            return Response({'success': False, 'error': 'Kayıt oluşturulamadı.'}, status=500)

    first_error = next(iter(serializer.errors.values()))[0] if serializer.errors else "Geçersiz veri."
    return Response({'success': False, 'error': first_error}, status=400)

@ratelimit(key='ip', rate='10/m', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([])
def logout_view(request):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)
    logout(request)
    return Response({'success': True})

@ratelimit(key='ip', rate='30/m', method='GET', block=False)
@api_view(['GET'])
@permission_classes([])
def get_user_profile(request):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    target_username = request.GET.get('username')

    if target_username:
        user = get_object_or_404(User, username__iexact=target_username)
    else:
        if request.user.is_authenticated:
            user = request.user
        else:
            return Response({'error': 'Kullanıcı bulunamadı.'}, status=404)
    
    word_stats = Word.objects.filter(user=user, status='approved').aggregate(
        total_words=Count('id'),
        total_score=Sum('score')
    )
    comment_count = Comment.objects.filter(user=user).count()
    
    return Response({
        'username': user.username,
        'date_joined': user.date_joined.strftime('%d.%m.%Y'),
        'word_count': word_stats['total_words'] or 0,
        'comment_count': comment_count,
        'total_score': word_stats['total_score'] or 0
    })

@ratelimit(key=universal_rate_key, rate='3/h', method='PATCH', block=False)
@api_view(['PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def change_password(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'İşlem limiti aşıldı.'}, status=429)

    user = request.user
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')

    if not current_password:
        return Response({'success': False, 'error': 'Mevcut şifrenizi girmeniz gerekiyor.'}, status=400)
    if len(current_password) > 60:
        return Response({'success': False, 'error': 'Mevcut şifre hatalı.'}, status=400)

    if not authenticate(request, username=user.username, password=current_password):
        return Response({'success': False, 'error': 'Mevcut şifre hatalı.'}, status=400)

    if not new_password or len(new_password) < 6:
        return Response({'success': False, 'error': 'Yeni şifre en az 6 karakter olmalı.'}, status=400)
    if len(new_password) > 60:
        return Response({'success': False, 'error': 'Yeni şifre en fazla 60  karakter olabilir.'}, status=400)

    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as e:
        return Response({'success': False, 'error': e.messages[0]}, status=400)

    user.set_password(new_password)
    user.save()
    update_session_auth_hash(request, user)
    
    return Response({'success': True, 'message': 'Şifreniz başarıyla güncellendi.'})

@ratelimit(key=universal_rate_key, rate='2/d', method='PATCH', block=False)
@api_view(['PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def change_username(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Kullanıcı adı değiştirme limiti aşıldı.'}, status=429)

    serializer = ChangeUsernameSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        new_username = serializer.validated_data['new_username'].lower()
        user = request.user

        try:
            with transaction.atomic():
                user.username = new_username
                user.save()
                
                return Response({'success': True, 'message': 'Kullanıcı adı başarıyla değiştirildi.'})
                
        except Exception:
            return Response({'success': False, 'error': 'Veritabanı güncelleme hatası.'}, status=500)
    
    first_error = next(iter(serializer.errors.values()))[0]
    return Response({'success': False, 'error': first_error}, status=400)
    
@ratelimit(key='ip', rate='60/m', method='GET', block=False)
@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([])
def get_my_words(request):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    target_username = request.GET.get('username')
    page_number = request.GET.get('page', 1)
    try:
        limit = int(request.GET.get('limit', 20))
    except (ValueError, TypeError):
        limit = 20
    limit = min(limit, 50)
    
    if target_username:
        user = get_object_or_404(User, username__iexact=target_username)
    elif request.user.is_authenticated:
        user = request.user
    else:
        return Response({'success': False, 'error': 'Yetkisiz erişim.'}, status=401)

    words_qs = Word.objects.filter(user=user, status='approved')\
        .annotate(comment_count=Count('comments'))\
        .select_related('user')\
        .prefetch_related('categories')\
        .order_by('-timestamp')
    
    paginator = Paginator(words_qs, limit)
    try:
        words_page = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        words_page = []

    user_votes = {}
    
    try:
        if words_page and request.user.is_authenticated:
            page_word_ids = [w.id for w in words_page]
            votes = WordVote.objects.filter(user=request.user, word_id__in=page_word_ids).values('word', 'value')
            for v in votes:
                user_votes[v['word']] = v['value']
    except (DatabaseError, OperationalError):
        pass

    serializer = WordSerializer(words_page, many=True, context={'user_votes': user_votes})

    return Response({
        'success': True,
        'words': serializer.data,
        'total_count': paginator.count
    })

# --- BİLDİRİM (NOTIFICATION) ENDPOINTLERİ ---

@ratelimit(key=universal_rate_key, rate='60/m', method='GET', block=False)
@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    page_number = request.GET.get('page', 1)
    limit = min(int(request.GET.get('limit', 20)), 50)

    # Filtering strictly for active notifications to prevent spam
    qs = Notification.objects.filter(recipient=request.user, is_active=True).select_related(
        'actor', 'word', 'comment', 'challenge_comment', 'challenge_comment__challenge'
    )
    paginator = Paginator(qs, limit)
    try:
        page = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page = []

    serializer = NotificationSerializer(page, many=True)

    return Response({
        'success': True,
        'notifications': serializer.data,
        'has_next': page.has_next() if hasattr(page, 'has_next') else False,
    })


@ratelimit(key=universal_rate_key, rate='120/m', method='GET', block=False)
@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_unread_count(request):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    cache_key = f'notif_unread_{request.user.id}'
    count = cache.get(cache_key)
    if count is None:
        count = Notification.objects.filter(recipient=request.user, is_read=False, is_active=True).count()
        cache.set(cache_key, count, 60)
    return Response({'success': True, 'unread_count': count})


@ratelimit(key=universal_rate_key, rate='30/m', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    ids = request.data.get('ids')
    qs = Notification.objects.filter(recipient=request.user, is_read=False, is_active=True)
    
    if ids is not None:
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            return Response({'success': False, 'error': 'Geçersiz ID formatı.'}, status=400)
        qs = qs.filter(id__in=ids)
    else:
        return Response({'success': False, 'error': 'İşaretlenecek bildirim ID\'leri eksik.'}, status=400)
        
    qs.update(is_read=True)
    cache.delete(f'notif_unread_{request.user.id}')

    return Response({'success': True})