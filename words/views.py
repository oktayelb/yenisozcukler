# words/views.py
"""Sözcük alanının tüm uçları: sözcükler, kategoriler, yorumlar ve oylama.

Yorum bir sözcüğün parçası (zorunlu CASCADE FK), bu yüzden burada duruyor.
`vote` uç noktası hem sözcüğe hem yoruma oy verir; ikisi de bu uygulamada
olduğu için artık dışarıdan bir model import etmesi gerekmiyor; yalnızca
bildirim yazarken `notifications.Notification` kullanılır.
"""

import logging
import random

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication

from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.db.models import Count, F, Q
from django.db import transaction, DatabaseError, OperationalError, IntegrityError

from core.http import verify_turnstile, get_client_ip, universal_rate_key
from logs.logger import log_activity
from notifications.models import Notification
from .models import Word, WordVote, Category, Comment, CommentVote
from .serializers import (
    WordSerializer, WordCreateSerializer, WordAddExampleSerializer, CategorySerializer,
    CommentSerializer, CommentCreateSerializer,
)

logger = logging.getLogger(__name__)


@ratelimit(key='ip', rate='600/m', method='GET', block=False)
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

@ratelimit(key='ip', rate='1000/m', method='GET', block=False)
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

    # Anonim varsayılan akış yanıtı tüm ziyaretçiler için aynıdır; 45 sn
    # önbelleğe alınır. Girişli kullanıcı yanıtı user_votes içerdiği için
    # önbelleğe alınmaz. Anahtar uzayı bilinçli olarak dar tutuluyor
    # (whitelist'li sort, sayfa 1-10, varsayılan limit): keyfi parametreler
    # locmem önbelleğini şişirip sıcak girdileri düşüremesin.
    try:
        page_int = int(page_number)
    except (ValueError, TypeError):
        page_int = 0
    feed_cacheable = (
        not request.user.is_authenticated
        and not search_query
        and not tag_slug
        and sort in ('date_desc', 'date_asc', 'score_desc', 'score_asc')
        and limit == 20
        and 1 <= page_int <= 10
    )
    if feed_cacheable:
        feed_cache_key = f'words_feed:{page_int}:{sort}'
        cached_payload = cache.get(feed_cache_key)
        if cached_payload is not None:
            return Response(cached_payload)

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

    payload = {
        'status': 'full',
        'words': serializer.data,
        'total_count': total_count
    }
    if feed_cacheable:
        cache.set(feed_cache_key, payload, 45)
    return Response(payload)

@ratelimit(key='ip', rate='1000/m', method='GET', block=False)
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

@ratelimit(key='ip', rate='1000/m', method='GET', block=False)
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

@ratelimit(key='ip', rate='120/m', method='GET', block=False)
@api_view(['GET'])
@permission_classes([])
def get_random_word(request):
    """Rastgele onaylanmış bir sözcüğü döndürür (zar butonu)."""
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    cache_key = 'approved_word_slugs'
    exclude = request.GET.get('exclude', '')

    # Havuz bayatsa (silinmiş/onayı kalkmış sözcük) bir kez yenileyip tekrar dene
    for attempt in range(2):
        slugs = cache.get(cache_key)
        if slugs is None:
            slugs = list(
                Word.objects.filter(status='approved')
                    .exclude(slug__isnull=True)
                    .exclude(slug='')
                    .values_list('slug', flat=True)
            )
            cache.set(cache_key, slugs, 60 * 5)

        if not slugs:
            return Response({'success': False, 'error': 'Sözcük bulunamadı.'}, status=404)

        # Aynı sözcüğü art arda vermemek için mevcut olanı havuzdan çıkar
        pool = [s for s in slugs if s != exclude] or slugs

        word = (
            Word.objects.filter(status='approved', slug=random.choice(pool))
                .annotate(comment_count=Count('comments'))
                .select_related('user')
                .prefetch_related('categories')
                .first()
        )
        if word:
            break
        cache.delete(cache_key)
    else:
        return Response({'success': False, 'error': 'Sözcük bulunamadı.'}, status=404)

    user_votes = {}
    if request.user.is_authenticated:
        vote = WordVote.objects.filter(user=request.user, word=word).values('value').first()
        if vote:
            user_votes[word.id] = vote['value']

    serializer = WordSerializer(word, context={'user_votes': user_votes})
    return Response({'success': True, 'word': serializer.data})

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
        
        log_activity(request, detail=f'"{word.word}" (#{word.id}) onay bekliyor')
        return Response({'success': True})
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        log_activity(request, detail=f'Reddedildi: {first_error}')
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
        log_activity(request, detail=f'"{word.word}" (#{word.id})')
        return Response({'success': True, 'message': 'Örnek cümle başarıyla eklendi.'})

    first_error = next(iter(serializer.errors.values()))[0]
    return Response({'success': False, 'error': first_error}, status=400)

@ratelimit(key='ip', rate='300/m', method='GET', block=False)
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


# --- YORUM VE OYLAMA ---

@ratelimit(key='ip', rate='1000/m', method='GET', block=False)
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

    log_activity(
        request,
        detail=f'{entity_type} #{entity_id} {action} -> {response_action}'
    )
    return Response({
        'success': True,
        'new_score': obj.score,
        'user_action': response_action
    })

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

        log_activity(request, detail=f'"{word.word}" (#{word.id}): {new_comment.comment[:80]}')
        return Response({'success': True, 'comment': CommentSerializer(new_comment).data}, status=201)
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        log_activity(request, detail=f'Reddedildi: {first_error}')
        return Response({'success': False, 'error': first_error}, status=400)
    
