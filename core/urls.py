from django.urls import path, re_path
from . import views

urlpatterns = [
    # robots.txt
    path('robots.txt', views.robots_txt, name='robots_txt'),

    # Ana Sayfa (Bot-aware)
    path('', views.index_view, name='index'),

    # SEO: Server-side rendered word detail (bots) / SPA shell (browsers)
    path('sozcuk/<int:word_id>/', views.word_detail, name='word_detail'),

    # GET API
    path('api/words', views.get_words, name='get_words'),
    path('api/word/<int:word_id>', views.get_word, name='get_word'),
    path('api/comments/<int:word_id>', views.get_comments, name='get_comments'),
    path('api/categories', views.get_categories, name='get_categories'),
    path('api/my-words', views.get_my_words, name='get_my_words'),

    # POST API
    path('api/word', views.add_word, name='add_word'),
    path('api/comment', views.add_comment, name='add_comment'),
    path('api/vote/<str:entity_type>/<int:entity_id>', views.vote, name='vote'),
    path('api/login', views.login_view, name='login'),
    path('api/register', views.register_view, name='register'),
    path('api/logout', views.logout_view, name='logout'),
    path('api/profile', views.get_user_profile, name='get_user_profile'),

    # PATCH API
    path('api/password', views.change_password, name='change_password'),
    path('api/username', views.change_username, name='change_username'),
    path('api/example', views.add_example, name='add_example'),

    # Notifications
    path('api/notifications', views.get_notifications, name='get_notifications'),
    path('api/notifications/unread-count', views.get_unread_count, name='get_unread_count'),
    path('api/notifications/mark-read', views.mark_notifications_read, name='mark_notifications_read'),

    # SPA catch-all (Bot-aware)
    path('kategori/<slug:slug>/', views.category_view, name='spa_category'),

    # Catch-all: serve SPA shell for any unmatched path (must be last)
    re_path(r'^(?!api/).*$', views.spa_catchall, name='spa_catchall'),
]