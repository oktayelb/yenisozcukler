from django.db import models

class Word(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
    ]

    word = models.CharField(max_length=50)
    definition = models.CharField(max_length=300)
    author = models.CharField(max_length=20, default='Anonymous')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.word

class UserLike(models.Model):
    # İstenen Değişiklik: CharField yerine GenericIPAddressField kullanıldı
    ip_address = models.GenericIPAddressField()
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='likes')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensures one like per IP per word
        unique_together = ('ip_address', 'word')

class Comment(models.Model):
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='comments')
    author = models.CharField(max_length=50, default='Anonim') # Eski haline geri alındı
    comment = models.CharField(max_length=200)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author}: {self.comment[:20]}"