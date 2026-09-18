from django.urls import path, re_path
from django.views.generic import RedirectView
from . import views, seo

urlpatterns = [
    # robots.txt
    path('robots.txt', seo.robots_txt, name='robots_txt'),
    path('sitemap.xml', seo.sitemap_xml, name='sitemap_xml'),
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True), name='favicon_ico'),

    # Ana Sayfa (Bot-aware)
    path('', seo.index_view, name='index'),

    # SEO: Server-side rendered word detail (bots) / SPA shell (browsers)
    path('sozcuk/<slug:word_slug>/', seo.word_detail, name='word_detail'),

    # Notifications
    path('api/notifications', views.get_notifications, name='get_notifications'),
    path('api/notifications/unread-count', views.get_unread_count, name='get_unread_count'),
    path('api/notifications/mark-read', views.mark_notifications_read, name='mark_notifications_read'),

    # SPA catch-all (Bot-aware)
    path('kategori/<slug:slug>/', seo.category_view, name='spa_category'),

    # Catch-all: serve SPA shell for any unmatched path (must be last)
    re_path(r'^(?!api/).*$', seo.spa_catchall, name='spa_catchall'),
]