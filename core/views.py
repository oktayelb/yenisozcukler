# core/views.py
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication

from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.db.models import Count, F, Sum
from django.db import transaction

from .models import Word, Comment, WordVote, CommentVote, Category
from .serializers import (
    WordSerializer, CommentSerializer, 
    WordCreateSerializer, CommentCreateSerializer,
    AuthSerializer, ChangeUsernameSerializer,
    WordAddExampleSerializer, CategorySerializer
)

# --- YARDIMCI FONKSİYONLAR ---

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
    limit = int(request.GET.get('limit', 20))
    limit = min(limit, 50)
    mode = request.GET.get('mode', 'all') 
    tag_slug = request.GET.get('tag') 
    sort = request.GET.get('sort', 'date_desc')

    words_queryset = Word.objects.filter(status='approved')\
        .annotate(comment_count=Count('comments'))\
        .prefetch_related('categories')\
        .only('id', 'word', 'definition', 'example', 'etymology', 'author', 'timestamp', 'is_profane', 'score')

    if sort == 'date_asc':
        words_queryset = words_queryset.order_by('timestamp')
    elif sort == 'score_desc':
        words_queryset = words_queryset.order_by('-score', '-timestamp')
    elif sort == 'score_asc':
        words_queryset = words_queryset.order_by('score', '-timestamp')
    else:
        words_queryset = words_queryset.order_by('-timestamp')
    
    if mode == 'profane':
        words_queryset = words_queryset.filter(is_profane=True)
    else:  
        words_queryset = words_queryset.filter(is_profane=False)
    
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
                
    except Exception:
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
    limit = int(request.GET.get('limit', 10))
    limit = min(limit, 20)

    comments_qs = Comment.objects.filter(word_id=word_id).order_by('timestamp')
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
    except Exception:
        pass

    serializer = CommentSerializer(comments_page, many=True, context={'user_votes': user_votes})
    
    return Response({
        'success': True, 
        'comments': serializer.data,
        'has_next': comments_page.has_next() if hasattr(comments_page, 'has_next') else False
    })

# --- YAZMA (WRITE) ENDPOINTLERİ ---

@ratelimit(key='ip', rate='100/m', method='POST', block=False)
@ratelimit(key=universal_rate_key, rate='15/m', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])  # VOTE REMAINS STRICTLY LOCKED TO USERS
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
            existing_vote.save()
            obj.score = F('score') + (vote_val * 2)
            response_action = 'liked' if vote_val == 1 else 'disliked'
    else:
        new_vote = VoteClass(
            value=vote_val, 
            ip_address=client_ip, 
            user=user,             
            **{lookup_field: obj}
        )
        new_vote.save()
        obj.score = F('score') + vote_val
        response_action = 'liked' if vote_val == 1 else 'disliked'

    obj.save()
    obj.refresh_from_db()

    return Response({
        'success': True, 
        'new_score': obj.score, 
        'user_action': response_action 
    })

@ratelimit(key='ip', rate='30/m', method='POST', block=False)
@ratelimit(key=universal_rate_key, rate='5/m', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([])  # OPENED TO ANONYMOUS USERS
def add_word(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)
    
    serializer = WordCreateSerializer(data=request.data)
    
    if serializer.is_valid():
        client_ip = get_client_ip(request)
        save_kwargs = {'status': 'pending', 'ip_address': client_ip}
        
        if request.user.is_authenticated:
            save_kwargs['user'] = request.user
            save_kwargs['author'] = request.user.username
        else:
            save_kwargs['author'] = 'Anonim'
        
        serializer.save(**save_kwargs)
        cache.delete_many(['total_approved_words_count_all', 'total_approved_words_count_profane'])
        
        return Response({'success': True})
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)

@ratelimit(key='ip', rate='20/m', method='PATCH', block=False)
@ratelimit(key=universal_rate_key, rate='5/m', method='PATCH', block=False)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def add_example(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    serializer = WordAddExampleSerializer(data=request.data)
    
    if serializer.is_valid():
        word_id = serializer.validated_data['word_id']
        new_example = serializer.validated_data['example']
        word = get_object_or_404(Word, id=word_id)

        if word.user != request.user:
            return Response({'success': False, 'error': 'Bu kelimeyi düzenleme yetkiniz yok.'}, status=403)

        if word.example and word.example.strip():
            return Response({'success': False, 'error': 'Bu kelimenin zaten bir örnek cümlesi var.'}, status=400)

        word.example = new_example
        word.save()
        return Response({'success': True, 'message': 'Örnek cümle başarıyla eklendi.'})

    first_error = next(iter(serializer.errors.values()))[0]
    return Response({'success': False, 'error': first_error}, status=400)

@ratelimit(key='ip', rate='50/m', method='POST', block=False)
@ratelimit(key=universal_rate_key, rate='10/m', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([]) # OPENED TO ANONYMOUS USERS
def add_comment(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    serializer = CommentCreateSerializer(data=request.data)
    
    if serializer.is_valid():
        word = get_object_or_404(Word, id=serializer.validated_data['word_id'])
        
        user_obj = request.user if request.user.is_authenticated else None
        author_name = request.user.username if user_obj else 'Anonim'
            
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
    
## Profil İşlemleri

@ratelimit(key='ip', rate='20/m', method='POST', block=False)
@ratelimit(key='post:username', rate='5/10m', method='POST', block=False)
@api_view(['POST'])
@permission_classes([])
def login_view(request):
    if getattr(request, 'limited', False):
         return Response({'success': False, 'error': 'Çok fazla giriş denemesi. Lütfen bekleyin.'}, status=429)

    serializer = AuthSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        user = authenticate(request, username=username, password=password)  
        if user is None:
            return Response({'success': False, 'error': 'Bu kullanıcı adı veya şifre hatalı.'}, status=400)
        
        login(request, user)    

        return Response({'success': True, 'username': user.username, 'message': 'Giriş başarılı.'})
    
    first_error = next(iter(serializer.errors.values()))[0] if serializer.errors else "Geçersiz veri."
    return Response({'success': False, 'error': first_error}, status=400)

@ratelimit(key='ip', rate='10/h', method='POST', block=False)
@ratelimit(key=universal_rate_key, rate='2/h', method='POST', block=False)
@api_view(['POST'])
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
            with transaction.atomic():
                user = User.objects.create_user(username=username, password=password)
                login(request, user)
                return Response({'success': True, 'username': user.username, 'message': 'Kayıt başarılı.'}, status=201)
        except Exception as e:
            return Response({'success': False, 'error': 'Kayıt oluşturulamadı.'}, status=500)

    first_error = next(iter(serializer.errors.values()))[0] if serializer.errors else "Geçersiz veri."
    return Response({'success': False, 'error': first_error}, status=400)

@api_view(['POST'])
@permission_classes([])
def logout_view(request):
    logout(request)
    return Response({'success': True})

@ratelimit(key='ip', rate='120/m', method='GET', block=False)
@api_view(['GET'])
@permission_classes([]) 
def get_user_profile(request):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    target_username = request.GET.get('username')

    if target_username:
        user = get_object_or_404(User, username=target_username)
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
@permission_classes([IsAuthenticated])
def change_password(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'İşlem limiti aşıldı.'}, status=429)

    user = request.user
    new_password = request.data.get('new_password')
    
    if not new_password or len(new_password) < 6:
        return Response({'success': False, 'error': 'Şifre en az 6 karakter olmalı.'}, status=400)
    
    user.set_password(new_password)
    user.save()
    update_session_auth_hash(request, user)
    
    return Response({'success': True, 'message': 'Şifreniz başarıyla güncellendi.'})

@ratelimit(key=universal_rate_key, rate='2/d', method='PATCH', block=False)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def change_username(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Kullanıcı adı değiştirme limiti aşıldı.'}, status=429)

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
                
        except Exception:
            return Response({'success': False, 'error': 'Veritabanı güncelleme hatası.'}, status=500)
    
    first_error = next(iter(serializer.errors.values()))[0]
    return Response({'success': False, 'error': first_error}, status=400)
    
@ratelimit(key='ip', rate='60/m', method='GET', block=False)
@api_view(['GET'])
@permission_classes([]) 
def get_my_words(request):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    target_username = request.GET.get('username')
    page_number = request.GET.get('page', 1)
    limit = int(request.GET.get('limit', 20))
    limit = min(limit, 50)
    
    if target_username:
        user = get_object_or_404(User, username=target_username)
    elif request.user.is_authenticated:
        user = request.user
    else:
        return Response({'success': False, 'error': 'Yetkisiz erişim.'}, status=401)

    words_qs = Word.objects.filter(user=user, status='approved').order_by('-timestamp')
    
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
    except Exception:
        pass

    serializer = WordSerializer(words_page, many=True, context={'user_votes': user_votes})
    
    return Response({
        'success': True, 
        'words': serializer.data,
        'total_count': paginator.count
    })