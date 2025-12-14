# core/views.py
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from .models import Word, UserLike, Comment
from .serializers import WordSerializer, CommentSerializer

def get_client_ip(request):
    # 1. Adım: Cloudflare'den gelen özel başlığa bak (En Güvenlisi)
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    
    if cf_ip:
        return cf_ip

    # 2. Adım: Eğer Cloudflare başlığı yoksa (örn: kendi bilgisayarında çalışıyorsan)
    # Standart IP alma yöntemine dön.
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
        
    return request.META.get('REMOTE_ADDR')

@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def get_words(request):
    approved_words = Word.objects.filter(status='approved').order_by('-timestamp')[:50]
    total_count = Word.objects.filter(status='approved').count()
    
    client_ip = get_client_ip(request)
    liked_word_ids = set()
    if client_ip:
        liked_word_ids = set(UserLike.objects.filter(ip_address=client_ip).values_list('word_id', flat=True))

    serializer = WordSerializer(approved_words, many=True, context={'liked_ids': liked_word_ids})
    return Response({'status': 'full', 'words': serializer.data, 'total_count': total_count})

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

@ratelimit(key='ip', rate='1/15s', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
def add_word(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz. Lütfen bekleyin.'}, status=429)

    ip = get_client_ip(request)
    if not ip:
        return Response({'success': False, 'error': 'IP Hatası.'}, status=400)
    
    data = request.data
    word_text = data.get('word', '').strip()
    definition = data.get('definition', '').strip()
    nickname = data.get('nickname', '').strip()
    is_profane = data.get('is_profane', False)
    Word.objects.create(
        word=word_text, 
        definition=definition, 
        author=nickname, 
        status='pending',
        is_profane=is_profane
        )
    return Response({'success': True})

@ratelimit(key='ip', rate='1/15s', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
def add_comment(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz. Lütfen bekleyin.'}, status=429)

    ip = get_client_ip(request)
    if not ip:
        return Response({'success': False, 'error': 'IP Hatası.'}, status=400)
    
    data = request.data
    word_id = data.get('word_id')
    comment_text = data.get('comment', '').strip()
    author = data.get('author', 'Anonim').strip()
    
    word = get_object_or_404(Word, id=word_id)
    new_comment = Comment.objects.create(word=word, author=author[:50], comment=comment_text)
    return Response({'success': True, 'comment': CommentSerializer(new_comment).data}, status=201)

@api_view(['GET'])
@authentication_classes([]) 
@permission_classes([])
def get_comments(request, word_id):
    comments = Comment.objects.filter(word_id=word_id).order_by('timestamp')
    serializer = CommentSerializer(comments, many=True)
    return Response({'success': True, 'comments': serializer.data})