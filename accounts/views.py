# accounts/views.py
"""Kimlik doğrulama ve profil uçları.

Kendi modeli yoktur; `django.contrib.auth.User` üzerine oturur. Sözcük/yorum
sayaçları için `core.models`'i okur — bağımlılık tek yönlüdür
(accounts -> core), `core` buraya hiç bakmaz.
"""

import logging

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication

from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Sum
from django.db import transaction, IntegrityError

from words.models import Word, Comment
from core.text import turkish_lower
from core.http import verify_turnstile, universal_rate_key, login_username_key
from .serializers import AuthSerializer, ChangeUsernameSerializer

logger = logging.getLogger(__name__)


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

    username = turkish_lower(request.data.get('username', '').strip())
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
        username = serializer.validated_data['username']
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

@ratelimit(key='ip', rate='300/m', method='GET', block=False)
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
        new_username = serializer.validated_data['new_username']
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
    
