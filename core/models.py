from django.db import models
from django.contrib.auth.models import User  # User modelini ekledik

class Word(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
    ]
    
    # --- YENİ EKLENEN ALAN ---
    # Mevcut verileri bozmamak için null=True, blank=True
    # Kullanıcı silinirse sözcük silinmesin, sadece user bağı kopsun (SET_NULL)
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='words',
        db_index=True
    )
    # -------------------------

    is_profane = models.BooleanField(default=False)
    word = models.CharField(max_length=50)
    definition = models.CharField(max_length=300)
    
    # Author alanı duruyor. Anonimse buraya yazılan string,
    # üyeyse User'ın username'i veya display_name'i buraya kopyalanabilir (denormalizasyon).
    author = models.CharField(max_length=50, default='Anonim')    
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    score = models.IntegerField(default=0, db_index=True)

    def __str__(self):
        return self.word

class Comment(models.Model):
    # --- YENİ EKLENEN ALAN ---
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='comments',
        db_index=True
    )
    # -------------------------

    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='comments')
    author = models.CharField(max_length=50, default='Anonim')
    comment = models.CharField(max_length=200, blank=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    score = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.author}: {self.comment[:20]}"


# --- VOTE MODELLERİ ---

class WordVote(models.Model):
    VALUE_CHOICES = [
        (1, 'Like'),
        (-1, 'Dislike')
    ]
    
    # --- YENİ EKLENEN ALAN ---
    # Oylarda kullanıcı silinirse oyun da silinmesini tercih edebiliriz (CASCADE).
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='word_votes',
        db_index=True
    )
    # -------------------------

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    session_id = models.CharField(max_length=40, db_index=True)
    
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='votes')
    value = models.SmallIntegerField(choices=VALUE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        # DİKKAT: Şimdilik unique constraint'i ('session_id', 'word') olarak bırakıyoruz.
        # İleride hem session hem user kontrolü yapan karmaşık bir constraint veya 
        # kod tarafında validasyon gerekebilir. Şimdilik migration'ı patlatmamak için dokunmuyoruz.
        unique_together = ('session_id', 'word')

class CommentVote(models.Model):
    VALUE_CHOICES = [
        (1, 'Like'),
        (-1, 'Dislike')
    ]
    
    # --- YENİ EKLENEN ALAN ---
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='comment_votes',
        db_index=True
    )
    # -------------------------

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    session_id = models.CharField(max_length=40, db_index=True)
    
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='votes')
    value = models.SmallIntegerField(choices=VALUE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session_id', 'comment')