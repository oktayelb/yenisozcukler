# core/views.py
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
# from django.utils.html import escape # GÜNCELLEME: Manuel XSS temizliği kaldırıldı
from .models import Word, UserLike, Comment
from .serializers import WordSerializer, CommentSerializer
import re
# import time # GÜNCELLEME: Global rate limit mekanizması kaldırıldığı için gerek kalmadı

# --- YARDIMCILAR (IP ve Rate Limit) ---
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')

ALPHANUM_WITH_SPACES = re.compile(r'^[a-zA-ZçÇğĞıIİöÖşŞüÜ\s.,0-9-]*$')
# GÜNCELLEME: Üretimde çalışmayacağı için global rate limit sözlükleri kaldırıldı.
# user_last_post_time = {}
# user_last_comment_time = {} 

# --- PUBLIC API VIEW FONKSİYONLARI ---
# Bu view'larda yetki aranmaz (authentication_classes ve permission_classes boş)

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

    # GÜNCELLEME: Serializer'a 'liked_ids' context'i gönderiliyor.
    serializer = WordSerializer(approved_words, many=True, context={'liked_ids': liked_word_ids})
    return Response({'status': 'full', 'words': serializer.data, 'total_count': total_count})


@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
def toggle_like(request, word_id):
    client_ip = get_client_ip(request)
    if not client_ip: return Response({'success': False, 'error': 'IP adresi alınamadı.'}, status=400)
    word = get_object_or_404(Word, id=word_id)
    if word.status != 'approved': return Response({'success': False, 'error': 'Geçersiz sözcük'}, status=404)
    
    # GÜNCELLEME: GenericIPAddressField kullanıldığı için IP adresi modelde otomatik doğrulanır.
    existing_like = UserLike.objects.filter(ip_address=client_ip, word=word).first()
    
    if existing_like:
        existing_like.delete()
        action = 'unliked'
    else:
        UserLike.objects.create(ip_address=client_ip, word=word)
        action = 'liked'
        
    return Response({'success': True, 'action': action, 'new_likes': word.likes.count(), 'word_id': word.id})


@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
def add_word(request):
    ip = get_client_ip(request)
    if not ip: return Response({'success': False, 'error': 'IP Hatası.'}, status=400)
    
    # GÜNCELLEME: Rate limit kontrolü kaldırıldı (Dış sistemlere taşınmalı).
    # current_time = time.time()
    # if ip in user_last_post_time and (current_time - user_last_post_time.get(ip, 0) < 30):
    #     return Response({'success': False, 'error': 'Çok hızlı işlem yapıyorsunuz. Bekleyin.'}, status=429)

    data = request.data
    word_text = data.get('word', '').strip()
    definition = data.get('definition', '').strip()
    nickname = data.get('nickname', '').strip()
    
    # ... (Validasyonlar)
    
    # GÜNCELLEME: escape() fonksiyonu çağrıları kaldırıldı. 
    # Sanitizasyon Model/Serializer katmanında yapılmalıdır.
    Word.objects.create(word=word_text, definition=definition, author=nickname, status='pending')
    # user_last_post_time[ip] = current_time # Kaldırıldı
    return Response({'success': True})


@api_view(['POST'])
@authentication_classes([]) 
@permission_classes([])
def add_comment(request):
    ip = get_client_ip(request)
    if not ip: return Response({'success': False, 'error': 'IP Hatası.'}, status=400)
    
    data = request.data
    word_id = data.get('word_id')
    comment_text = data.get('comment', '').strip()
    author = data.get('author', 'Anonim').strip()
    
    # ... (Validasyonlar)
    
    word = get_object_or_404(Word, id=word_id)
    # GÜNCELLEME: escape() fonksiyonu çağrıları kaldırıldı.
    new_comment = Comment.objects.create(word=word, author=author[:50], comment=comment_text)
    return Response({'success': True, 'comment': CommentSerializer(new_comment).data}, status=201)

@api_view(['GET'])
@authentication_classes([]) 
@permission_classes([])
def get_comments(request, word_id):
    comments = Comment.objects.filter(word_id=word_id).order_by('timestamp')
    serializer = CommentSerializer(comments, many=True)
    return Response({'success': True, 'comments': serializer.data})
