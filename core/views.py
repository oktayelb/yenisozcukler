# core/views.py
import logging

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication

from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.db.models import F
from django.db import transaction, DatabaseError, OperationalError, IntegrityError

from words.models import Word, WordVote
from .models import Comment, CommentVote, Notification
from .serializers import (
    CommentSerializer, CommentCreateSerializer, NotificationSerializer,
)
from common.http import verify_turnstile, get_client_ip, universal_rate_key

logger = logging.getLogger(__name__)


# --- OKUMA (READ) ENDPOINTLERİ ---

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
