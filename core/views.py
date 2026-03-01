# core/views.py
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.db.models import Count, F , Sum 
from django.db import transaction

import uuid
from .models import Word, Comment, WordVote, CommentVote, Category
from .serializers import (
    WordSerializer, CommentSerializer, 
    WordCreateSerializer, CommentCreateSerializer,
    AuthSerializer, ChangeUsernameSerializer,
    WordAddExampleSerializer, CategorySerializer
)

# --- YARDIMCI FONKSİYONLAR ---

def get_client_ip(request):
    """
    Retrieves the client IP.
    SECURITY WARNING: This function trusts the CF-Connecting-IP and X-Forwarded-For headers.
    Because you do not have a local reverse proxy (like Nginx), this is ONLY secure if you 
    have configured your OS firewall (e.g., UFW) to block all traffic to this server EXCEPT 
    from trusted sources like Cloudflare's IP ranges.
    """
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf_ip:
        return cf_ip
        
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()

    return request.META.get('REMOTE_ADDR')

def get_valid_session_id(request):
    """
    Attempts to retrieve and cryptographically verify the session ID from the cookie.
    Returns None if the cookie is missing, tampered with, or forged.
    """
    try:
        return request.get_signed_cookie('user_id', salt='vote_session')
    except Exception:
        return None

def get_or_create_session_id(request):
    return get_valid_session_id(request) or str(uuid.uuid4())

# --- OKUMA (READ) ENDPOINTLERİ ---

@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def get_categories(request):
    """
    Returns the list of active categories for the frontend to render pills/hashtags.
    """
    cache_key = 'all_active_categories'
    categories_data = cache.get(cache_key)
    
    if not categories_data:
        categories = Category.objects.filter(is_active=True)
        serializer = CategorySerializer(categories, many=True)
        categories_data = serializer.data
        cache.set(cache_key, categories_data, 60 * 60) # Cache for 1 hour

    return Response({'success': True, 'categories': categories_data})

@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def get_words(request):
    page_number = request.GET.get('page', 1)
    limit = int(request.GET.get('limit', 20))
    limit = min(limit, 50)
    mode = request.GET.get('mode', 'all') 
    tag_slug = request.GET.get('tag') 

    # --- QUERYSET FIX ---
    # Removed .select_related('user') to fix the FieldError with .only()
    words_queryset = Word.objects.filter(status='approved')\
        .annotate(comment_count=Count('comments'))\
        .prefetch_related('categories')\
        .only('id', 'word', 'definition', 'example', 'author', 'timestamp', 'is_profane', 'score')\
        .order_by('-timestamp')
    
    # 1. Profanity Filter
    if mode == 'profane':
        words_queryset = words_queryset.filter(is_profane=True)
    else:  
        words_queryset = words_queryset.filter(is_profane=False)
    
    # 2. Tag (Category) Filter
    if tag_slug:
        words_queryset = words_queryset.filter(categories__slug=tag_slug)

    if not tag_slug:
        cache_key = f'total_approved_words_count_{mode}'
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

    session_id = get_valid_session_id(request)
    user_votes = {}
    
    try:
        if words_page:
            page_word_ids = [w.id for w in words_page]
            votes = []

            if request.user.is_authenticated:
                votes = WordVote.objects.filter(
                    user=request.user, 
                    word_id__in=page_word_ids
                ).values('word', 'value')
            elif session_id:
                votes = WordVote.objects.filter(
                    session_id=session_id, 
                    word_id__in=page_word_ids
                ).values('word', 'value')
            
            for v in votes:
                user_votes[v['word']] = v['value']
                
    except Exception as e:
        print(f"Word Vote Fetch Error: {e}")
        pass

    serializer = WordSerializer(words_page, many=True, context={'user_votes': user_votes})
    
    response = Response({
        'status': 'full', 
        'words': serializer.data, 
        'total_count': total_count
    })
    
    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_signed_cookie('user_id', session_id, salt='vote_session', max_age=31536000, httponly=True)
        
    return response

@api_view(['GET'])
@authentication_classes([]) 
@permission_classes([])
def get_comments(request, word_id):
    page = request.GET.get('page', 1)
    limit = int(request.GET.get('limit', 10))
    limit = min(limit, 20)

    comments_qs = Comment.objects.filter(word_id=word_id).order_by('timestamp')
    paginator = Paginator(comments_qs, limit)

    try:
        comments_page = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        comments_page = []

    session_id = get_valid_session_id(request)
    user_votes = {} 

    try:
        if comments_page:
            page_comment_ids = [c.id for c in comments_page]
            votes = []

            if request.user.is_authenticated:
                votes = CommentVote.objects.filter(
                    user=request.user,
                    comment_id__in=page_comment_ids
                ).values('comment', 'value')
            elif session_id:
                votes = CommentVote.objects.filter(
                    session_id=session_id,
                    comment_id__in=page_comment_ids
                ).values('comment', 'value')

            for v in votes:
                user_votes[v['comment']] = v['value']
    except Exception as e:
        print(f"Comment Vote Fetch Error: {e}")
        pass

    serializer = CommentSerializer(comments_page, many=True, context={'user_votes': user_votes})
    
    response = Response({
        'success': True, 
        'comments': serializer.data,
        'has_next': comments_page.has_next() if hasattr(comments_page, 'has_next') else False
    })
    
    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_signed_cookie('user_id', session_id, salt='vote_session', max_age=31536000, httponly=True)

    return response

# --- YAZMA (WRITE) ENDPOINTLERİ ---
@ratelimit(key='ip', rate='3/5s', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
@transaction.atomic 
def vote(request, entity_type, entity_id):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    client_ip = get_client_ip(request)
    session_id = get_or_create_session_id(request)
    user = request.user if request.user.is_authenticated else None
    
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

    existing_vote = None

    if user:
        existing_vote = VoteClass.objects.filter(user=user, **{lookup_field: obj}).first()
        if not existing_vote:
            stray_vote = VoteClass.objects.filter(session_id=session_id, user__isnull=True, **{lookup_field: obj}).first()
            if stray_vote:
                existing_vote = stray_vote
                existing_vote.user = user 
    else:
        existing_vote = VoteClass.objects.filter(session_id=session_id, **{lookup_field: obj}).first()

    response_action = 'none'

    if existing_vote:
        if existing_vote.value == vote_val:
            existing_vote.delete()
            obj.score = F('score') - vote_val
            response_action = 'none'
        else:
            existing_vote.value = vote_val
            if user: existing_vote.user = user 
            existing_vote.save()
            obj.score = F('score') + (vote_val * 2)
            response_action = 'liked' if vote_val == 1 else 'disliked'
    else:
        new_vote = VoteClass(
            value=vote_val, 
            ip_address=client_ip, 
            session_id=session_id, 
            user=user,             
            **{lookup_field: obj}
        )
        new_vote.save()
        obj.score = F('score') + vote_val
        response_action = 'liked' if vote_val == 1 else 'disliked'

    obj.save()
    obj.refresh_from_db()

    response = Response({
        'success': True, 
        'new_score': obj.score, 
        'user_action': response_action 
    })
    response.set_signed_cookie('user_id', session_id, salt='vote_session', max_age=31536000, httponly=True)
    return response

@ratelimit(key='ip', rate='2/15s', method='POST', block=False)
@api_view(['POST'])
@permission_classes([])
def add_word(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)
    
    serializer = WordCreateSerializer(data=request.data)
    if serializer.is_valid():
        client_ip = get_client_ip(request)

        save_kwargs = {
            'status': 'pending',
            'ip_address': client_ip 
        }
        
        if request.user.is_authenticated:
            save_kwargs['user'] = request.user
            save_kwargs['author'] = request.user.username
        
        serializer.save(**save_kwargs)
        
        cache.delete('total_approved_words_count_all')
        cache.delete('total_approved_words_count_profane')
        return Response({'success': True})
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)

@ratelimit(key='ip', rate='5/m', method='POST', block=False)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_example(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    serializer = WordAddExampleSerializer(data=request.data)
    
    if serializer.is_valid():
        word_id = serializer.validated_data['word_id']
        new_example = serializer.validated_data['example']

        word = get_object_or_404(Word, id=word_id)

        # 1. Kullanıcı bu kelimenin sahibi mi?
        if word.user != request.user:
            return Response({
                'success': False, 
                'error': 'Bu kelimeyi düzenleme yetkiniz yok.'
            }, status=403)

        # 2. Zaten örnek cümle var mı? (Sadece 1 kez izin veriyoruz)
        if word.example and word.example.strip():
            return Response({
                'success': False, 
                'error': 'Bu kelimenin zaten bir örnek cümlesi var.'
            }, status=400)

        word.example = new_example
        word.save()

        return Response({'success': True, 'message': 'Örnek cümle başarıyla eklendi.'})

    else:
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)

@ratelimit(key='ip', rate='1/15s', method='POST', block=False)
@api_view(['POST'])
@permission_classes([])
def add_comment(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    serializer = CommentCreateSerializer(data=request.data)
    if serializer.is_valid():
        word = get_object_or_404(Word, id=serializer.validated_data['word_id'])
        
        author_name = serializer.validated_data.get('author', 'Anonim')
        user_obj = None
        
        if request.user.is_authenticated:
            user_obj = request.user
            author_name = request.user.username
            
        new_comment = Comment.objects.create(
            word=word,
            author=author_name,
            comment=serializer.validated_data['comment'],
            user=user_obj, 
            score=0
        )
        return Response({'success': True, 'comment': CommentSerializer(new_comment).data}, status=201)
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)
    
##profil işlemleri
@ratelimit(key='ip', rate='1/10s', method='POST', block=True)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def login_view(request):
    serializer = AuthSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        if not User.objects.filter(username=username).exists():
            return Response({'success': False, 'error': 'Bu kullanıcı adı kayıtlı değil.'}, status=404)
        
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({'success': False, 'error': 'Şifre hatalı.'}, status=400)
        
        login(request, user)
        return Response({
            'success': True, 
            'username': user.username, 
            'message': 'Giriş başarılı.'
        })
    
    first_error = next(iter(serializer.errors.values()))[0] if serializer.errors else "Geçersiz veri."
    return Response({'success': False, 'error': first_error}, status=400)

@ratelimit(key='ip', rate='1/6000s', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def register_view(request):
    if getattr(request, 'limited', False):
         return Response({'success': False, 'error': 'Çok fazla kayıt denemesi. Lütfen daha sonra tekrar deneyin.'}, status=429)

    serializer = AuthSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        if User.objects.filter(username=username).exists():
            return Response({'success': False, 'error': 'Bu kullanıcı adı zaten alınmış.'}, status=400)
        
        try:
            user = User.objects.create_user(username=username, password=password)
            
            Word.objects.filter(author__iexact=username, user__isnull=True).update(user=user)
            Comment.objects.filter(author__iexact=username, user__isnull=True).update(user=user)
            
            login(request, user)
            return Response({
                'success': True, 
                'username': user.username, 
                'message': 'Kayıt başarılı.'
            }, status=201)
        except Exception as e:
            return Response({'success': False, 'error': 'Kayıt oluşturulamadı.'}, status=500)

    first_error = next(iter(serializer.errors.values()))[0] if serializer.errors else "Geçersiz veri."
    return Response({'success': False, 'error': first_error}, status=400)

@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def logout_view(request):
    logout(request)
    return Response({'success': True})

@api_view(['GET'])
@permission_classes([]) 
def get_user_profile(request):
    target_username = request.GET.get('username')

    if target_username:
        user = get_object_or_404(User, username=target_username)
    else:
        if request.user.is_authenticated:
            user = request.user
        else:
            return Response({'error': 'Kullanıcı bulunamadı.'}, status=404)
    
    word_count = Word.objects.filter(user=user, status='approved').count()
    comment_count = Comment.objects.filter(user=user).count()
    total_score = Word.objects.filter(user=user, status='approved').aggregate(Sum('score'))['score__sum'] or 0
    
    return Response({
        'username': user.username,
        'date_joined': user.date_joined.strftime('%d.%m.%Y'),
        'word_count': word_count,
        'comment_count': comment_count,
        'total_score': total_score
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    new_password = request.data.get('new_password')
    
    if not new_password or len(new_password) < 6:
        return Response({'success': False, 'error': 'Şifre en az 6 karakter olmalı.'}, status=400)
    
    user.set_password(new_password)
    user.save()
    update_session_auth_hash(request, user)
    
    return Response({'success': True, 'message': 'Şifreniz başarıyla güncellendi.'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_username(request):
    serializer = ChangeUsernameSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        new_username = serializer.validated_data['new_username']
        user = request.user

        try:
            with transaction.atomic():
                user.username = new_username
                user.save()

                Word.objects.filter(user=user).update(author=new_username)
                Comment.objects.filter(user=user).update(author=new_username)
                
                return Response({'success': True, 'message': 'Kullanıcı adı başarıyla değiştirildi.'})
                
        except Exception as e:
            return Response({'success': False, 'error': 'Veritabanı güncelleme hatası.'}, status=500)
    
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)
    
@api_view(['GET'])
@permission_classes([]) 
def get_my_words(request):
    target_username = request.GET.get('username')
    
    if target_username:
        user = get_object_or_404(User, username=target_username)
    elif request.user.is_authenticated:
        user = request.user
    else:
        return Response({'success': False, 'error': 'Yetkisiz erişim.'}, status=401)

    words = Word.objects.filter(user=user, status='approved').order_by('-timestamp')
    
    session_id = get_valid_session_id(request)
    user_votes = {}
    try:
        if words:
            page_word_ids = [w.id for w in words]
            votes = []
            if request.user.is_authenticated:
                votes = WordVote.objects.filter(user=request.user, word_id__in=page_word_ids).values('word', 'value')
            elif session_id:
                votes = WordVote.objects.filter(session_id=session_id, word_id__in=page_word_ids).values('word', 'value')
            for v in votes:
                user_votes[v['word']] = v['value']
    except:
        pass

    serializer = WordSerializer(words, many=True, context={'user_votes': user_votes})
    return Response({'success': True, 'words': serializer.data})