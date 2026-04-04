from django.urls import path
from . import views
from django.views.generic import TemplateView

urlpatterns = [
    # Ana Sayfa ve Public API'ler
    path('', TemplateView.as_view(template_name='index.html'), name='index'),
    
    # GET
    path('api/words', views.get_words, name='get_words'),
    path('api/comments/<int:word_id>', views.get_comments, name='get_comments'),
    path('api/categories', views.get_categories, name='get_categories'),
    path('api/my-words', views.get_my_words, name='get_my_words'),

    # POST
    path('api/word', views.add_word, name='add_word'),
    path('api/comment', views.add_comment, name='add_comment'),
    path('api/vote/<str:entity_type>/<int:entity_id>', views.vote, name='vote'),   
    path('api/login', views.login_view, name='login'),
    path('api/register', views.register_view, name='register'),
    path('api/logout', views.logout_view, name='logout'),
    path('api/profile', views.get_user_profile, name='get_user_profile'),

    # PATCH
    path('api/password', views.change_password, name='change_password'),
    path('api/username', views.change_username, name='change_username'),
    path('api/example', views.add_example, name='add_example'),
]