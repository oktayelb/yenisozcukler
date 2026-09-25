from rest_framework.decorators import permission_classes

from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse, HttpResponseNotFound

from words.models import Word, Category

from .http import is_bot


_ROBOTS_TXT = (
    "User-agent: GPTBot\n"
    "Disallow: /\n"
    "\n"
    "User-agent: OAI-SearchBot\n"
    "Allow: /\n"
    "Disallow: /api/\n"
    "Disallow: /admin/\n"
    "\n"
    "User-agent: ChatGPT-User\n"
    "Allow: /\n"
    "Disallow: /api/\n"
    "Disallow: /admin/\n"
    "\n"
    "User-agent: Googlebot\n"
    "Allow: /\n"
    "Disallow: /api/\n"
    "Disallow: /admin/\n"
    "\n"
    "User-agent: Googlebot-Image\n"
    "Allow: /\n"
    "Disallow: /api/\n"
    "Disallow: /admin/\n"
    "\n"
    "User-agent: Bingbot\n"
    "Allow: /\n"
    "Disallow: /api/\n"
    "Disallow: /admin/\n"
    "\n"
    "User-agent: DuckDuckBot\n"
    "Allow: /\n"
    "Disallow: /api/\n"
    "Disallow: /admin/\n"
    "\n"
    "User-agent: Applebot\n"
    "Allow: /\n"
    "Disallow: /api/\n"
    "Disallow: /admin/\n"
    "\n"
    "User-agent: *\n"
    "Allow: /\n"
    "Disallow: /api/\n"
    "Disallow: /admin/\n"
    "\n"
    "Sitemap: https://yenisozcukler.com/sitemap.xml\n"
)

def robots_txt(request):
    return HttpResponse(_ROBOTS_TXT, content_type='text/plain')

def sitemap_xml(request):
    words = (
        Word.objects
        .filter(status='approved', slug__isnull=False)
        .exclude(slug='')
        .only('slug', 'timestamp')
        .order_by('-timestamp')
    )
    categories = (
        Category.objects
        .filter(is_active=True)
        .only('slug')
        .order_by('order', 'name')
    )
    latest_word = words.first()
    return render(
        request,
        'sitemap.xml',
        {
            'words': words,
            'categories': categories,
            'latest_word': latest_word,
        },
        content_type='application/xml',
    )



@permission_classes([])
def index_view(request):
    if is_bot(request.META.get('HTTP_USER_AGENT')):
        words = Word.objects.filter(status='approved').select_related('user').order_by('-timestamp')[:50]
        response = render(request, 'bot_index.html', {'words': words})
    else:
        response = render(request, 'index.html')
    
    response['Vary'] = 'User-Agent'
    return response

@permission_classes([])
def category_view(request, slug):
    if is_bot(request.META.get('HTTP_USER_AGENT')):
        category = get_object_or_404(Category, slug=slug)
        words = Word.objects.filter(status='approved', categories=category).select_related('user').order_by('-timestamp')[:50]
        response = render(request, 'bot_category.html', {'category': category, 'words': words})
    else:
        response = render(request, 'index.html')
        
    response['Vary'] = 'User-Agent'
    return response

@permission_classes([])
def word_detail(request, word_slug):
    if is_bot(request.META.get('HTTP_USER_AGENT')):
        word = get_object_or_404(
            Word.objects.select_related('user').prefetch_related('categories'),
            slug=word_slug,
            status='approved'
        )
        response = render(request, 'word_detail.html', {'word': word})
    else:
        response = render(request, 'index.html')

    response['Vary'] = 'User-Agent'
    return response

@permission_classes([])
def spa_catchall(request, *args, **kwargs):
    if is_bot(request.META.get('HTTP_USER_AGENT')):
        return HttpResponseNotFound()
    return render(request, 'index.html')
