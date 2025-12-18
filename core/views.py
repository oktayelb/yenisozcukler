# core/views.py
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache  # Cache importu
from .models import Word, UserLike, Comment
from .serializers import (
    WordSerializer, CommentSerializer, 
    WordCreateSerializer, CommentCreateSerializer
)

def get_client_ip(request):
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf_ip:
        return cf_ip
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')

@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def get_words(request):
    page_number = request.GET.get('page', 1)
    limit = int(request.GET.get('limit', 20))

    words_queryset = Word.objects.filter(status='approved').order_by('-timestamp')
    
    # 1. PERFORMANS: Cache kullanımı (5 dakika boyunca sayıyı tutar)
    cache_key = 'total_approved_words_count'
    total_count = cache.get(cache_key)
    if total_count is None:
        total_count = words_queryset.count()
        cache.set(cache_key, total_count, 60 * 5)

    paginator = Paginator(words_queryset, limit)

    try:
        words_page = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        words_page = []

    client_ip = get_client_ip(request)
    liked_word_ids = set()
    
    if client_ip and words_page:
        page_word_ids = [w.id for w in words_page]
        liked_word_ids = set(UserLike.objects.filter(
            ip_address=client_ip, 
            word_id__in=page_word_ids
        ).values_list('word_id', flat=True))

    serializer = WordSerializer(words_page, many=True, context={'liked_ids': liked_word_ids})
    
    return Response({
        'status': 'full', 
        'words': serializer.data, 
        'total_count': total_count
    })

@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
def toggle_like(request, word_id):
    client_ip = get_client_ip(request)
    if not client_ip:
        return Response({'success': False, 'error': 'IP adresi alınamadı.'}, status=400)
    
    word = get_object_or_404(Word, id=word_id)
    if word.status != 'approved':
        return Response({'success': False, 'error': 'Geçersiz sözcük'}, status=404)
    
    existing_like = UserLike.objects.filter(ip_address=client_ip, word=word).first()
    
    if existing_like:
        existing_like.delete()
        action = 'unliked'
    else:
        UserLike.objects.create(ip_address=client_ip, word=word)
        action = 'liked'
        
    return Response({'success': True, 'action': action, 'new_likes': word.likes.count(), 'word_id': word.id})

@ratelimit(key='ip', rate='14/15s', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
def add_word(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    # 2. CLEAN CODE: Validasyon mantığı Serializer'a taşındı
    serializer = WordCreateSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(status='pending') # Default status ataması
        return Response({'success': True})
    else:
        # İlk hatayı döndür
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)

@ratelimit(key='ip', rate='1/15s', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
def add_comment(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    ip = get_client_ip(request)
    if not ip:
        return Response({'success': False, 'error': 'IP Hatası.'}, status=400)
    
    serializer = CommentCreateSerializer(data=request.data)
    if serializer.is_valid():
        word = get_object_or_404(Word, id=serializer.validated_data['word_id'])
        new_comment = Comment.objects.create(
            word=word,
            author=serializer.validated_data['author'],
            comment=serializer.validated_data['comment']
        )
        # Yanıt için Read Serializer kullanıyoruz
        return Response({'success': True, 'comment': CommentSerializer(new_comment).data}, status=201)
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)

@api_view(['GET'])
@authentication_classes([]) 
@permission_classes([])
def get_comments(request, word_id):
    # 3. PERFORMANS: Yorumlar için sayfalama (Pagination)
    page = request.GET.get('page', 1)
    limit = int(request.GET.get('limit', 10))

    comments_qs = Comment.objects.filter(word_id=word_id).order_by('timestamp')
    paginator = Paginator(comments_qs, limit)

    try:
        comments_page = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        comments_page = []

    serializer = CommentSerializer(comments_page, many=True)
    
    return Response({
        'success': True, 
        'comments': serializer.data,
        'has_next': comments_page.has_next() if isinstance(comments_page, (list, object)) and hasattr(comments_page, 'has_next') else False,
        'next_page_number': comments_page.next_page_number() if hasattr(comments_page, 'has_next') and comments_page.has_next() else None
    })