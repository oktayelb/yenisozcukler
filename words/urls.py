from django.urls import path
from . import views

urlpatterns = [
    # GET
    path('api/words', views.get_words, name='get_words'),
    path('api/word/<int:word_id>', views.get_word, name='get_word'),
    path('api/word-by-slug/<slug:word_slug>', views.get_word_by_slug, name='get_word_by_slug'),
    path('api/categories', views.get_categories, name='get_categories'),
    path('api/my-words', views.get_my_words, name='get_my_words'),
    path('api/random-word', views.get_random_word, name='get_random_word'),

    # POST / PATCH
    path('api/word', views.add_word, name='add_word'),
    path('api/example', views.add_example, name='add_example'),
]
