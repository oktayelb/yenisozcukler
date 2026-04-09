from django.db import models
from django.contrib.auth.models import User
import re


TURKISH_CHAR_MAP = {
    'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
    'â': 'a', 'î': 'i', 'û': 'u',
}


def turkish_to_ascii(text):
    text = text.lower()
    for tr, en in TURKISH_CHAR_MAP.items():
        text = text.replace(tr, en)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def generate_unique_slug(word_text, exclude_id=None):
    base = turkish_to_ascii(word_text)
    slug = base
    qs = Word.objects.all()
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    counter = 2
    while qs.filter(slug=slug).exists():
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

    @property
    def display_author(self):
        if self.user:
            return self.user.username
        return self.author

    def __str__(self):
        return self.word

class Comment(models.Model):
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='comments',
        db_index=True
    )

    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='comments')
    author = models.CharField(max_length=50, default='Anonim')
    comment = models.CharField(max_length=200, blank=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    score = models.IntegerField(default=0)

    @property
    def display_author(self):
        if self.user:
            return self.user.username
        return self.author

    def __str__(self):
        return f"{self.display_author}: {self.comment[:20]}"


# --- VOTE MODELS ---

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

class CommentVote(models.Model):
    VALUE_CHOICES = [
        (1, 'Like'),
        (-1, 'Dislike')
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='comment_votes',
        db_index=True
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='votes')
    value = models.SmallIntegerField(choices=VALUE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'comment')


class Notification(models.Model):
    TYPE_CHOICES = [
        ('word_vote', 'Word Vote'),
        ('comment_vote', 'Comment Vote'),
        ('new_comment', 'New Comment'),
        ('challenge_win', 'Challenge Win'),
        ('word_rejected', 'Word Rejected'),
        ('challenge_rejected', 'Challenge Rejected'),
    ]

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    word = models.ForeignKey(Word, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)

    message = models.CharField(max_length=300, blank=True, default='')
    is_read = models.BooleanField(default=False, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.notification_type} -> {self.recipient.username}"
