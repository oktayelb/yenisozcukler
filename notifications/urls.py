from django.urls import path
from . import views

urlpatterns = [
    path('api/notifications', views.get_notifications, name='get_notifications'),
    path('api/notifications/unread-count', views.get_unread_count, name='get_unread_count'),
    path('api/notifications/mark-read', views.mark_notifications_read, name='mark_notifications_read'),
]
