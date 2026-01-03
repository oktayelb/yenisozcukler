# core/views.py
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.db.models import F
from django.db import transaction
import uuid
from django.views.decorators.csrf import csrf_exempt
from .models import Word, Comment, WordVote, CommentVote
from .serializers import (
    WordSerializer, CommentSerializer, 
    WordCreateSerializer, CommentCreateSerializer
)
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from .serializers import AuthSerializer


def get_client_ip(request):
    return request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('REMOTE_ADDR')

def get_or_create_session_id(request):
    # 'user_id' burada çerez ismidir (Cookie Name).
    # Değeri ise her kullanıcı için unique UUID'dir.
    return request.COOKIES.get('user_id') or str(uuid.uuid4())

# --- OKUMA (READ) ENDPOINTLERİ ---

@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def get_words(request):
    page_number = request.GET.get('page', 1)
    limit = int(request.GET.get('limit', 20))
    limit = min(limit, 50)
    mode = request.GET.get('mode', 'all') 

    # Temel Sorgu
    words_queryset = Word.objects.filter(status='approved')\
        .only('id', 'word', 'definition', 'author', 'timestamp', 'is_profane', 'score')\
        .order_by('-timestamp')
    
    if mode == 'profane':
        words_queryset = words_queryset.filter(is_profane=True)
    else:  
        words_queryset = words_queryset.filter(is_profane=False)
        
    cache_key = f'total_approved_words_count_{mode}'
    total_count = cache.get(cache_key)
    
    if total_count is None:
        total_count = words_queryset.count()
        cache.set(cache_key, total_count, 60 * 5)

    paginator = Paginator(words_queryset, limit)
    try:
        words_page = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        words_page = []

    # --- OYLARI GETİRME (GÜNCELLENDİ: Auth + Guest) ---
    session_id = request.COOKIES.get('user_id')
    user_votes = {}
    
    try:
        if words_page:
            page_word_ids = [w.id for w in words_page]
            votes = []

            # 1. Kullanıcı giriş yapmışsa USER tablosundan çek
            if request.user.is_authenticated:
                votes = WordVote.objects.filter(
                    user=request.user, 
                    word_id__in=page_word_ids
                ).values('word', 'value')
            
            # 2. Giriş yapmamışsa ama Session ID varsa SESSION'dan çek
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
    
    # Session cookie yoksa oluştur
    if not session_id:
        response.set_cookie('user_id', str(uuid.uuid4()), max_age=31536000, httponly=True)
        
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

    session_id = request.COOKIES.get('user_id')
    user_votes = {} 

    try:
        if comments_page:
            page_comment_ids = [c.id for c in comments_page]
            votes = []

            # 1. Kullanıcı giriş yapmışsa USER tablosundan çek
            if request.user.is_authenticated:
                votes = CommentVote.objects.filter(
                    user=request.user,
                    comment_id__in=page_comment_ids
                ).values('comment', 'value')

            # 2. Giriş yapmamışsa SESSION'dan çek
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
        response.set_cookie('user_id', str(uuid.uuid4()), max_age=31536000, httponly=True)

    return response

# --- YAZMA (WRITE) ENDPOINTLERİ ---

@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
@transaction.atomic 
def vote(request, entity_type, entity_id):
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

    # Veritabanını kilitle (Concurrency)
    obj = get_object_or_404(ModelClass.objects.select_for_update(), id=entity_id)
    
    if entity_type == 'word' and obj.status != 'approved':
        return Response({'error': 'Geçersiz içerik.'}, status=404)

    # --- OY BULMA MANTIĞI ---
    existing_vote = None

    if user:
        # 1. Kullanıcı ise önce kendi adına kayıtlı oya bak
        existing_vote = VoteClass.objects.filter(user=user, **{lookup_field: obj}).first()
        
        # 2. Kendi adına yoksa, anonimken verdiği oyu (Session ID) bul ve sahiplen
        if not existing_vote:
            stray_vote = VoteClass.objects.filter(session_id=session_id, user__isnull=True, **{lookup_field: obj}).first()
            if stray_vote:
                existing_vote = stray_vote
                existing_vote.user = user # Oyu sahiplen
    else:
        # 3. Misafir ise sadece Session ID ile bak
        existing_vote = VoteClass.objects.filter(session_id=session_id, **{lookup_field: obj}).first()

    response_action = 'none'

    # --- OYLAMA İŞLEMİ ---
    if existing_vote:
        # Aynı oyu vermişse kaldır (Toggle)
        if existing_vote.value == vote_val:
            existing_vote.delete()
            obj.score = F('score') - vote_val
            response_action = 'none'
        # Farklı oy vermişse güncelle
        else:
            existing_vote.value = vote_val
            if user: existing_vote.user = user # User bilgisini güncelle
            existing_vote.save()
            obj.score = F('score') + (vote_val * 2)
            response_action = 'liked' if vote_val == 1 else 'disliked'
    else:
        # Yeni oy oluştur
        new_vote = VoteClass(
            value=vote_val, 
            ip_address=client_ip, 
            session_id=session_id, # Session ID her zaman loglanır
            user=user,             # Varsa user, yoksa None
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
    # Cookie süresini uzat
    response.set_cookie('user_id', session_id, max_age=31536000, httponly=True)
    
    return response

@ratelimit(key='ip', rate='2/15s', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
def add_word(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)
    
    serializer = WordCreateSerializer(data=request.data)
    if serializer.is_valid():
        save_kwargs = {'status': 'pending'}
        
        # Giriş yapmışsa User ve Author bilgisini ayarla
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

@ratelimit(key='ip', rate='1/15s', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
def add_comment(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    serializer = CommentCreateSerializer(data=request.data)
    if serializer.is_valid():
        word = get_object_or_404(Word, id=serializer.validated_data['word_id'])
        
        # Varsayılan değerler
        author_name = serializer.validated_data.get('author', 'Anonim')
        user_obj = None
        
        # Giriş yapmışsa override et
        if request.user.is_authenticated:
            user_obj = request.user
            author_name = request.user.username
            
        new_comment = Comment.objects.create(
            word=word,
            author=author_name,
            comment=serializer.validated_data['comment'],
            user=user_obj, # User'ı kaydet
            score=0
        )
        return Response({'success': True, 'comment': CommentSerializer(new_comment).data}, status=201)
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)
    
@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def unified_auth(request):
    """
    Tek endpoint: Hem Login hem Register.
    - Kullanıcı varsa -> Şifre kontrol et -> Giriş yap.
    - Kullanıcı yoksa -> Kaydet -> Giriş yap.
    """
    serializer = AuthSerializer(data=request.data)
    
    if serializer.is_valid():
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        
        # 1. Kullanıcı var mı kontrol et
        user_exists = User.objects.filter(username=username).exists()
        
        user = None
        action_taken = ""

        if user_exists:
            # Login Modu
            user = authenticate(request, username=username, password=password)
            if user is None:
                return Response({'success': False, 'error': 'Kullanıcı adı dolu, ancak şifre yanlış.'}, status=400)
            action_taken = "login"
        else:
            # Register Modu
            try:
                user = User.objects.create_user(username=username, password=password)
                action_taken = "register"
                # Not: create_user çalıştığı an signals.py devreye girer 
                # ve eski içerikleri bu user'a zimmetler.
            except Exception as e:
                return Response({'success': False, 'error': 'Kayıt oluşturulamadı.'}, status=400)

        # 2. Oturumu Başlat (Session Oluştur)
        if user:
            login(request, user)
            return Response({
                'success': True, 
                'username': user.username, 
                'action': action_taken,
                'message': f'Başarıyla {action_taken} işlemi yapıldı.'
            })
            
    # Validasyon hatası varsa
    first_error = next(iter(serializer.errors.values()))[0] if serializer.errors else "Geçersiz veri."
    return Response({'success': False, 'error': first_error}, status=400)