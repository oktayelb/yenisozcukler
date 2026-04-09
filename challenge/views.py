from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication

from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, F, Prefetch
from django.db import transaction, DatabaseError, OperationalError, IntegrityError

from core.views import get_client_ip, universal_rate_key
from .models import TranslationChallenge, ChallengeComment, ChallengeCommentVote
from .serializers import (
    TranslationChallengeSerializer, TranslationChallengeCreateSerializer,
    ChallengeCommentSerializer, ChallengeSuggestionCreateSerializer
)


@ratelimit(key='ip', rate='60/m', method='GET', block=False)
@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([])
def get_challenges(request):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    try:
        page = int(request.GET.get('page', 1))
    except (ValueError, TypeError):
        page = 1
        
    try:
        limit = int(request.GET.get('limit', 20))
    except (ValueError, TypeError):
        limit = 20
    limit = min(limit, 50)

    challenges_qs = (
        TranslationChallenge.objects.filter(status='approved')
        .annotate(comment_count=Count('comments'))
        .select_related('user')
        .prefetch_related(
            Prefetch(
                'comments',
                queryset=ChallengeComment.objects.order_by('-score', 'timestamp'),
                to_attr='prefetched_ordered_comments'
            )
        )
        .order_by('-comment_count', '-timestamp')
    )

    paginator = Paginator(challenges_qs, limit)
    try:
        challenges_page = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        challenges_page = []

    serializer = TranslationChallengeSerializer(challenges_page, many=True)
    return Response({
        'success': True,
        'challenges': serializer.data,
        'has_next': challenges_page.has_next() if hasattr(challenges_page, 'has_next') else False
    })


@ratelimit(key='ip', rate='30/m', method='POST', block=False)
@ratelimit(key=universal_rate_key, rate='5/m', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def add_challenge(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    serializer = TranslationChallengeCreateSerializer(data=request.data)
    if serializer.is_valid():
        client_ip = get_client_ip(request)
        TranslationChallenge.objects.create(
            foreign_word=serializer.validated_data['foreign_word'],
            meaning=serializer.validated_data['meaning'],
            user=request.user,
            ip_address=client_ip,
            status='pending'
        )
        return Response({'success': True})
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)


@ratelimit(key='ip', rate='120/m', method='GET', block=False)
@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([])
def get_challenge_comments(request, challenge_id):
    if getattr(request, 'limited', False):
        return Response({'error': 'Too many requests'}, status=429)

    challenge = get_object_or_404(TranslationChallenge, id=challenge_id, status='approved')

    try:
        page = int(request.GET.get('page', 1))
    except (ValueError, TypeError):
        page = 1
    try:
        limit = int(request.GET.get('limit', 10))
    except (ValueError, TypeError):
        limit = 10
    limit = min(limit, 20)

    comments_qs = ChallengeComment.objects.filter(challenge=challenge).select_related('user').order_by('-score', 'timestamp')
    paginator = Paginator(comments_qs, limit)

    try:
        comments_page = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        comments_page = []

    user_votes = {}
    try:
        if comments_page and request.user.is_authenticated:
            page_comment_ids = [c.id for c in comments_page]
            votes = ChallengeCommentVote.objects.filter(
                user=request.user,
                comment_id__in=page_comment_ids
            ).values('comment', 'value')
            for v in votes:
                user_votes[v['comment']] = v['value']
    except (DatabaseError, OperationalError):
        pass

    serializer = ChallengeCommentSerializer(comments_page, many=True, context={'user_votes': user_votes})

    has_submitted = False
    if request.user.is_authenticated:
        has_submitted = ChallengeComment.objects.filter(challenge=challenge, user=request.user).exists()

    winner_id = None
    if challenge.is_closed:
        top = ChallengeComment.objects.filter(challenge=challenge).order_by('-score', 'timestamp').first()
        if top and top.score > 0:
            winner_id = top.id

    return Response({
        'success': True,
        'comments': serializer.data,
        'has_next': comments_page.has_next() if hasattr(comments_page, 'has_next') else False,
        'is_closed': challenge.is_closed,
        'timer_on': challenge.timer_on,
        'has_submitted': has_submitted,
        'winner_id': winner_id,
    })


@ratelimit(key='ip', rate='50/m', method='POST', block=False)
@ratelimit(key=universal_rate_key, rate='10/m', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def add_challenge_suggestion(request):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    serializer = ChallengeSuggestionCreateSerializer(data=request.data)
    if serializer.is_valid():
        challenge = get_object_or_404(
            TranslationChallenge,
            id=serializer.validated_data['challenge_id'],
            status='approved'
        )

        if challenge.is_closed:
            return Response({
                'success': False,
                'error': 'Bu meydan okuma sona erdi, artık öneri eklenemez.'
            }, status=403)

        existing_by_user = ChallengeComment.objects.filter(
            challenge=challenge,
            user=request.user
        ).first()

        if existing_by_user:
            return Response({
                'success': False,
                'error': 'Bu meydan okumaya zaten bir öneri gönderdiniz.',
                'existing_id': existing_by_user.id
            }, status=409)

        suggested_word = serializer.validated_data['suggested_word']
        etymology = serializer.validated_data.get('etymology', '')
        example_sentence = serializer.validated_data.get('example_sentence', '')

        with transaction.atomic():
            existing_word = ChallengeComment.objects.select_for_update().filter(
                challenge=challenge,
                suggested_word__iexact=suggested_word
            ).first()

            if existing_word:
                return Response({
                    'success': False,
                    'error': 'duplicate',
                    'existing_id': existing_word.id
                }, status=409)

            try:
                new_suggestion = ChallengeComment.objects.create(
                    challenge=challenge,
                    user=request.user,
                    author=request.user.username,
                    suggested_word=suggested_word,
                    etymology=etymology,
                    example_sentence=example_sentence,
                    score=0
                )
            except IntegrityError:
                concurrent_existing = ChallengeComment.objects.filter(challenge=challenge, user=request.user).first()
                return Response({
                    'success': False,
                    'error': 'Bu meydan okumaya zaten bir öneri gönderdiniz.',
                    'existing_id': concurrent_existing.id if concurrent_existing else None
                }, status=409)

        return Response({
            'success': True,
            'suggestion': ChallengeCommentSerializer(new_suggestion).data
        }, status=201)
    else:
        first_error = next(iter(serializer.errors.values()))[0]
        return Response({'success': False, 'error': first_error}, status=400)


@ratelimit(key='ip', rate='100/m', method='POST', block=False)
@ratelimit(key=universal_rate_key, rate='15/m', method='POST', block=False)
@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
@transaction.atomic
def vote_challenge_comment(request, comment_id):
    if getattr(request, 'limited', False):
        return Response({'success': False, 'error': 'Çok fazla istek gönderdiniz.'}, status=429)

    client_ip = get_client_ip(request)
    user = request.user
    action = request.data.get('action')
    if action not in ['like', 'dislike']:
        return Response({'error': 'Geçersiz işlem.'}, status=400)

    comment = get_object_or_404(
        ChallengeComment.objects.select_for_update().select_related('challenge'),
        id=comment_id,
        challenge__status='approved'
    )

    if comment.challenge.is_closed:
        return Response({
            'success': False,
            'error': 'Bu meydan okuma sona erdi, artık oy verilemez.'
        }, status=403)

    vote_val = 1 if action == 'like' else -1
    existing_vote = ChallengeCommentVote.objects.filter(user=user, comment=comment).first()
    response_action = 'none'

    if existing_vote:
        if existing_vote.value == vote_val:
            existing_vote.delete()
            comment.score = F('score') - vote_val
            response_action = 'none'
        else:
            existing_vote.value = vote_val
            existing_vote.save()
            comment.score = F('score') + (vote_val * 2)
            response_action = 'liked' if vote_val == 1 else 'disliked'
    else:
        try:
            ChallengeCommentVote.objects.create(
                value=vote_val,
                ip_address=client_ip,
                user=user,
                comment=comment
            )
        except IntegrityError:
            return Response({'error': 'Oy zaten kaydedildi.'}, status=409)
        comment.score = F('score') + vote_val
        response_action = 'liked' if vote_val == 1 else 'disliked'

    comment.save()
    comment.refresh_from_db()

    owner = comment.user if hasattr(comment, 'user') else None
    if owner and owner != user:
        from core.models import Notification
        from django.core.cache import cache

        like_type = 'challenge_like'
        dislike_type = 'challenge_dislike'
        current_type = like_type if vote_val == 1 else dislike_type
        opposite_type = dislike_type if vote_val == 1 else like_type
        
        # Since Notification doesn't have a direct ChallengeComment FK, use `message`
        msg_id = f"challenge_comment_{comment.id}"

        if response_action == 'none':
            deleted, _ = Notification.objects.filter(
                recipient=owner, actor=user, notification_type=current_type, message=msg_id
            ).delete()
            if deleted:
                cache.delete(f'notif_unread_{owner.id}')
        else:
            Notification.objects.filter(
                recipient=owner, actor=user, notification_type=opposite_type, message=msg_id
            ).delete()
            
            _, created = Notification.objects.get_or_create(
                recipient=owner, actor=user, notification_type=current_type, message=msg_id
            )
            if created:
                cache.delete(f'notif_unread_{owner.id}')

    return Response({
        'success': True,
        'new_score': comment.score,
        'user_action': response_action
    })