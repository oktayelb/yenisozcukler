from django.db import models

class Word(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
    ]

    word = models.CharField(max_length=50)
    definition = models.CharField(max_length=300)
    author = models.CharField(max_length=20, default='Anonymous')
    
    # db_index=True eklendi: Sık sık 'status=approved' filtresi kullandığımız için sorguları hızlandırır.
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    
    # db_index=True eklendi: Ana sayfada sürekli zamana göre sıralama yapıldığı için performansı artırır.
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return self.word

class UserLike(models.Model):
    ip_address = models.GenericIPAddressField()
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='likes')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Aynı IP'nin aynı sözcüğe birden fazla oy vermesini engeller
        unique_together = ('ip_address', 'word')

class Comment(models.Model):
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='comments')
    author = models.CharField(max_length=50, default='Anonim')
    
    comment = models.CharField(max_length=200, blank=False)
    
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author}: {self.comment[:20]}"