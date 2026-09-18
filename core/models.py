from django.db import models
from django.contrib.auth.models import User


class Notification(models.Model):
    TYPE_CHOICES = [
        ('word_like', 'Word Like'),
        ('word_dislike', 'Word Dislike'),
        ('comment_like', 'Comment Like'),
        ('comment_dislike', 'Comment Dislike'),
        ('challenge_like', 'Challenge Like'),
        ('challenge_dislike', 'Challenge Dislike'),
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

    word = models.ForeignKey('words.Word', on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey('words.Comment', on_delete=models.CASCADE, null=True, blank=True)
    challenge_comment = models.ForeignKey('challenge.ChallengeComment', on_delete=models.CASCADE, null=True, blank=True)

    message = models.CharField(max_length=300, blank=True, default='')
    is_read = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)  # <-- NEW FIELD
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['recipient','is_active', 'is_read', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.notification_type} -> {self.recipient.username}"