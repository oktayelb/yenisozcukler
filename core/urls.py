from django.urls import path
from . import views
from django.views.generic import TemplateView

urlpatterns = [
    # Ana Sayfa ve Public API'ler
    path('', TemplateView.as_view(template_name='index.html'), name='index'),
    
    # Okuma (Read) İşlemleri
    path('api/words', views.get_words, name='get_words'),
    path('api/comments/<int:word_id>', views.get_comments, name='get_comments'),
    
    # Yazma (Write) İşlemleri
    path('api/add', views.add_word, name='add_word'),
    path('api/comment', views.add_comment, name='add_comment'),
    
    # --- YENİ OYLAMA ENDPOINT'İ ---
    # Eski 'api/like/...' kaldırıldı.
    # Artık tek bir endpoint var: /api/vote/word/5 veya /api/vote/comment/12 gibi çalışır.
    path('api/vote/<str:entity_type>/<int:entity_id>', views.vote, name='vote'),

    path('api/auth', views.unified_auth, name='unified_auth'),
    path('api/logout', views.logout_view, name='logout'),
    # ...
    path('api/profile', views.get_user_profile, name='get_user_profile'),
    path('api/change-password', views.change_password, name='change_password'),
    path('api/change-username', views.change_username, name='change_username'),

    path('api/my-words', views.get_my_words, name='get_my_words'),
]