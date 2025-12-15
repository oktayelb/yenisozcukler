from django.urls import path
from . import views
from django.views.generic import TemplateView

urlpatterns = [
    # Ana Sayfa ve Public API'ler
    path('', TemplateView.as_view(template_name='index.html'), name='index'),
    path('api/words', views.get_words, name='get_words'),
    path('api/like/<int:word_id>', views.toggle_like, name='toggle_like'),
    path('api/add', views.add_word, name='add_word'),
    path('api/comment', views.add_comment, name='add_comment'),
    path('api/comments/<int:word_id>', views.get_comments, name='get_comments'),
]


##git commit test