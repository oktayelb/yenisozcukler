# notifications/views.py
import logging

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication

from django_ratelimit.decorators import ratelimit
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache

from .models import Notification
from .serializers import NotificationSerializer
from common.http import universal_rate_key

logger = logging.getLogger(__name__)


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
