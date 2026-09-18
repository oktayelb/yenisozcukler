from django.db import models
from django.contrib.auth.models import User
from django.core.cache import cache

from common.text import turkish_to_ascii


def generate_unique_slug(word_text, exclude_id=None):
    base = turkish_to_ascii(word_text)
    qs = Word.objects.all()
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    existing = set(qs.filter(slug__startswith=base).values_list('slug', flat=True))
    slug = base
    counter = 2
    while slug in existing:
        slug = f'{base}{counter}'
        counter += 1
    return slug


REJECTION_REASONS = [
    ("Bu sözcük zaten Türkçede mevcut.", "Bu sözcük zaten Türkçede mevcut."),
    ("Tanım yeterince açık değil.", "Tanım yeterince açık değil."),
    ("Uygunsuz veya hakaret içerikli içerik.", "Uygunsuz veya hakaret içerikli içerik."),
    ("Sözcük daha önce önerilmiş.", "Sözcük daha önce önerilmiş."),
    ("Kök yapısı Türkçe dil kurallarına uygun değil.", "Kök yapısı Türkçe dil kurallarına uygun değil."),
]


class Category(models.Model):
    name = models.CharField(max_length=30)  
    slug = models.SlugField(unique=True)    
    description = models.CharField(max_length=150) 
    order = models.IntegerField(default=0)  
    is_active = models.BooleanField(default=True) 

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

class Word(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='words',
        db_index=True
    )

    categories = models.ManyToManyField(
        Category,
        related_name='words',
        blank=True
    )

    word = models.CharField(max_length=50)
    slug = models.SlugField(max_length=80, unique=True, null=True, db_index=True)
    definition = models.CharField(max_length=300)
    example = models.CharField(max_length=200, default="")
    etymology = models.CharField(max_length=200, default="")

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    author = models.CharField(max_length=50, default='Anonim')

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    rejection_reason = models.CharField(max_length=300, blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    score = models.IntegerField(default=0, db_index=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self.word, exclude_id=self.pk)
            
        super().save(*args, **kwargs)
        
        # Cache Invalidation: Clear this specific word's cache when edited or approved
        if self.slug:
            cache.delete(f'word_slug_{self.slug}')
        # Also clear the global approved words count so the feed stays accurate
        cache.delete('total_approved_words_count_all')
        cache.delete('approved_word_slugs')

    def delete(self, *args, **kwargs):
        # Cache Invalidation: Clear cache when a word is deleted (e.g. by an admin)
        if self.slug:
            cache.delete(f'word_slug_{self.slug}')
        cache.delete('total_approved_words_count_all')
        cache.delete('approved_word_slugs')
        
        super().delete(*args, **kwargs)

    @property
    def display_author(self):
        if self.user:
            return self.user.username
        return self.author

    def __str__(self):
        return self.word


class WordVote(models.Model):
    VALUE_CHOICES = [
        (1, 'Like'),
        (-1, 'Dislike')
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='word_votes',
        db_index=True
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='votes')
    value = models.SmallIntegerField(choices=VALUE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'word')
