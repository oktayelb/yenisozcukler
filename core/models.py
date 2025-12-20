from django.db import models

class Word(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
    ]
    is_profane = models.BooleanField(default=False)
    word = models.CharField(max_length=50)
    definition = models.CharField(max_length=300)
    author = models.CharField(max_length=50, default='Anonim')    
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Net Skor (Toplam Puan)
    score = models.IntegerField(default=0, db_index=True)

    def __str__(self):
        return self.word

class Comment(models.Model):
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='comments')
    author = models.CharField(max_length=50, default='Anonim')
    comment = models.CharField(max_length=200, blank=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    score = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.author}: {self.comment[:20]}"




# --- VOTE MODELLERİ (GÜNCELLENDİ) ---

class WordVote(models.Model):
    # ARTIK INTEGER: 1 (Like) veya -1 (Dislike)
    VALUE_CHOICES = [
        (1, 'Like'),
        (-1, 'Dislike')
    ]
    
    ip_address = models.GenericIPAddressField()
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='votes')
    
    # Değişiklik burada: CharField yerine SmallIntegerField
    value = models.SmallIntegerField(choices=VALUE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('ip_address', 'word')

class CommentVote(models.Model):
    VALUE_CHOICES = [
        (1, 'Like'),
        (-1, 'Dislike')
    ]
    
    ip_address = models.GenericIPAddressField()
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='votes')
    
    # Değişiklik burada
    value = models.SmallIntegerField(choices=VALUE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('ip_address', 'comment')