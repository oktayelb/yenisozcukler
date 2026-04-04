from django.urls import path
from . import views

urlpatterns = [
    path('api/challenges', views.get_challenges, name='get_challenges'),
    path('api/challenge', views.add_challenge, name='add_challenge'),
    path('api/challenge-comments/<int:challenge_id>', views.get_challenge_comments, name='get_challenge_comments'),
    path('api/challenge-suggestion', views.add_challenge_suggestion, name='add_challenge_suggestion'),
    path('api/challenge-comment-vote/<int:comment_id>', views.vote_challenge_comment, name='vote_challenge_comment'),
]
