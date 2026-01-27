from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=30)  # e.g., "Teknoloji"
    slug = models.SlugField(unique=True)    # e.g., "teknoloji" (URL friendly)
    description = models.CharField(max_length=150) # Tooltip text
    order = models.IntegerField(default=0)  # To control sorting in the list
    is_active = models.BooleanField(default=True) # To hide categories if needed without deleting

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

class Word(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='words',
        db_index=True
    )

    # --- NEW RELATIONSHIP ---
    categories = models.ManyToManyField(
        Category, 
        related_name='words', 
        blank=True
    )
    # ------------------------

    is_profane = models.BooleanField(default=False)
    word = models.CharField(max_length=50)
    definition = models.CharField(max_length=300)
    example = models.CharField(max_length=200, default="")
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    author = models.CharField(max_length=50, default='Anonim')    
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    score = models.IntegerField(default=0, db_index=True)

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

    def __str__(self):
        return f"{self.author}: {self.comment[:20]}"


# --- VOTE MODELS ---

class WordVote(models.Model):
    VALUE_CHOICES = [
        (1, 'Like'),
        (-1, 'Dislike')
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='word_votes',
        db_index=True
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    session_id = models.CharField(max_length=40, db_index=True)
    
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='votes')
    value = models.SmallIntegerField(choices=VALUE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session_id', 'word')

class CommentVote(models.Model):
    VALUE_CHOICES = [
        (1, 'Like'),
        (-1, 'Dislike')
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='comment_votes',
        db_index=True
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    session_id = models.CharField(max_length=40, db_index=True)
    
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='votes')
    value = models.SmallIntegerField(choices=VALUE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session_id', 'comment')