# core/views.py
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.db.models import F
from django.db import transaction
from .models import Word, Comment, WordVote, CommentVote
from .serializers import (
    WordSerializer, CommentSerializer, 
    WordCreateSerializer, CommentCreateSerializer
)

def get_client_ip(request):
    return request.META.get('HTTP_CF_CONNECTING_IP')

@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def get_words(request):
    page_number = request.GET.get('page', 1)
    limit = int(request.GET.get('limit', 20))
    limit = min(limit, 50)
    
    # Yeni parametre: mode
    mode = request.GET.get('mode', 'all') 

    # Temel sorgu
    words_queryset = Word.objects.filter(status='approved')\
        .only('id', 'word', 'definition', 'author', 'timestamp', 'is_profane', 'score')\
        .order_by('-timestamp')
    
    # EĞER mod 'profane' ise sadece +18 olanları getir
    if mode == 'profane':
        words_queryset = words_queryset.filter(is_profane=True)

    else :  
        words_queryset = words_queryset.filter(is_profane=False)
    # Cache key artık moda göre değişmeli, yoksa sayılar karışır
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

    client_ip = get_client_ip(request)
    user_votes = {}
    
    if client_ip and words_page:
        page_word_ids = [w.id for w in words_page]
        votes = WordVote.objects.filter(
            ip_address=client_ip, 
            word_id__in=page_word_ids
        ).values('word_id', 'value')
        
        for v in votes:
            user_votes[v['word_id']] = v['value']

    serializer = WordSerializer(words_page, many=True, context={'user_votes': user_votes})
    
    return Response({
        'status': 'full', 
        'words': serializer.data, 
        'total_count': total_count
    })
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

    client_ip = get_client_ip(request)
    user_votes = {} 

    if client_ip and comments_page:
        page_comment_ids = [c.id for c in comments_page]
        votes = CommentVote.objects.filter(
            ip_address=client_ip,
            comment_id__in=page_comment_ids
        ).values('comment_id', 'value')

        for v in votes:
            user_votes[v['comment_id']] = v['value']

    serializer = CommentSerializer(comments_page, many=True, context={'user_votes': user_votes})
    
    return Response({
        'success': True, 
        'comments': serializer.data,
        'has_next': comments_page.has_next() if hasattr(comments_page, 'has_next') else False
    })

@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
@transaction.atomic 
def vote(request, entity_type, entity_id):
    client_ip = get_client_ip(request)
    if not client_ip:
        return Response({'error': 'IP adresi alınamadı.'}, status=400)

    action = request.data.get('action') 
    if action not in ['like', 'dislike']:
        return Response({'error': 'Geçersiz işlem.'}, status=400)

    # STRING -> INTEGER DÖNÜŞÜMÜ
    # like ise +1, dislike ise -1
    vote_val = 1 if action == 'like' else -1

    # Model Sınıflarını Belirle
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

    # Veriyi kilitle (Lock)
    obj = get_object_or_404(ModelClass.objects.select_for_update(), id=entity_id)
    
    if entity_type == 'word' and obj.status != 'approved':
        return Response({'error': 'Geçersiz içerik.'}, status=404)

    filter_kwargs = {'ip_address': client_ip, lookup_field: obj}
    existing_vote = VoteClass.objects.filter(**filter_kwargs).first()

    response_action = 'none'

    if existing_vote:
        if existing_vote.value == vote_val:
            # AYNI OYU TEKRARLAMA (Örn: +1 varken tekrar +1) -> Oyu Sil
            existing_vote.delete()
            # Matematik: Skordan oy değerini çıkar (vote_val 1 ise -1 yapar, -1 ise +1 yapar)
            obj.score = F('score') - vote_val
            response_action = 'none'
        else:
            # OY DEĞİŞTİRME (SWITCH) (Örn: -1'den 1'e)
            existing_vote.value = vote_val
            existing_vote.save()
            
            # Matematik: Fark 2 birimdir. 
            # -1'den +1'e geçiş için +2 eklenmeli.
            # +1'den -1'e geçiş için -2 çıkarılmalı.
            # Bu da (vote_val * 2) demektir.
            obj.score = F('score') + (vote_val * 2)
            
            response_action = 'liked' if vote_val == 1 else 'disliked'
    else:
        # YENİ OY
        VoteClass.objects.create(value=vote_val, **filter_kwargs)
        obj.score = F('score') + vote_val
        response_action = 'liked' if vote_val == 1 else 'disliked'

    obj.save()
    obj.refresh_from_db()

    return Response({
        'success': True, 
        'new_score': obj.score, 
        'user_action': response_action 
    })

@ratelimit(key='ip', rate='1/15s', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
def add_word(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    serializer = WordCreateSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(status='pending')
        cache.delete('total_approved_words_count')
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

    ip = get_client_ip(request)
    if not ip:
        return Response({'success': False, 'error': 'IP Hatası.'}, status=400)
    
    serializer = CommentCreateSerializer(data=request.data)
    if serializer.is_valid():
        word = get_object_or_404(Word, id=serializer.validated_data['word_id'])
        new_comment = Comment.objects.create(
            word=word,
            author=serializer.validated_data['author'],
            comment=serializer.validated_data['comment'],
            score=0
        )
        return Response({'success': True, 'comment': CommentSerializer(new_comment).data}, status=201)
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)