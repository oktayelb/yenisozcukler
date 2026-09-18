from django.urls import path, re_path
from django.views.generic import RedirectView
from . import seo

urlpatterns = [
    # robots.txt
    path('robots.txt', seo.robots_txt, name='robots_txt'),
    path('sitemap.xml', seo.sitemap_xml, name='sitemap_xml'),
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True), name='favicon_ico'),
    path('', seo.index_view, name='index'),
    path('sozcuk/<slug:word_slug>/', seo.word_detail, name='word_detail'),
    path('kategori/<slug:slug>/', seo.category_view, name='spa_category'),
    re_path(r'^(?!api/).*$', seo.spa_catchall, name='spa_catchall'),
]