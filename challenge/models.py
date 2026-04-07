from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime


class TranslationChallenge(models.Model):
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
        related_name='challenges',
        db_index=True
    )

    foreign_word = models.CharField(max_length=100)
    meaning = models.CharField(max_length=300)
    author = models.CharField(max_length=50, default='Anonim')

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    rejection_reason = models.CharField(max_length=300, blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    timer_on = models.BooleanField(default=False)
    timer_started_at = models.DateTimeField(null=True, blank=True)
    winner_word_created = models.BooleanField(default=False)

    TIMER_DURATION = datetime.timedelta(days=7)

    @property
    def display_author(self):
        if self.user:
            return self.user.username
        return self.author

    @property
    def is_closed(self):
        if self.timer_on and self.timer_started_at:
            return timezone.now() >= self.timer_started_at + self.TIMER_DURATION
        return False

    @property
    def time_remaining(self):
        if self.timer_on and self.timer_started_at:
            end = self.timer_started_at + self.TIMER_DURATION
            remaining = end - timezone.now()
            if remaining.total_seconds() <= 0:
                return None
            return remaining
        return None

    def create_winner_word(self):
        from django.db import transaction
        from core.models import Word, Notification

        with transaction.atomic():
            locked = TranslationChallenge.objects.select_for_update().get(pk=self.pk)
            if not locked.is_closed or locked.winner_word_created:
                return None
            top = locked.comments.order_by('-score', 'timestamp').first()
            if not top or top.score <= 0:
                return None
            word = Word.objects.create(
                word=top.suggested_word,
                definition=locked.meaning[:300],
                etymology=(top.etymology or '')[:200],
                example=(top.example_sentence or '')[:200],
                user=top.user,
                author=top.display_author,
                status='approved',
            )
            locked.winner_word_created = True
            locked.save(update_fields=['winner_word_created'])

            # Notify the winner
            if top.user:
                Notification.objects.create(
                    recipient=top.user,
                    notification_type='challenge_win',
                    word=word,
                    message=f'"{top.suggested_word}" sözcüğünüz "{locked.foreign_word}" yarışmasını kazandı!',
                )

        self.winner_word_created = True
        return word

    def __str__(self):
        return self.foreign_word

    class Meta:
        ordering = ['-timestamp']
        db_table = 'core_translationchallenge'


class ChallengeComment(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='challenge_comments',
        db_index=True
    )

    challenge = models.ForeignKey(TranslationChallenge, on_delete=models.CASCADE, related_name='comments')
    author = models.CharField(max_length=50, default='Anonim')
    suggested_word = models.CharField(max_length=30, blank=False)
    etymology = models.CharField(max_length=200, blank=True, default='')
    example_sentence = models.CharField(max_length=200, blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)
    score = models.IntegerField(default=0)

    @property
    def display_author(self):
        if self.user:
            return self.user.username
        return self.author

    def __str__(self):
        return f"{self.display_author}: {self.suggested_word}"

    class Meta:
        db_table = 'core_challengecomment'
        unique_together = ('user', 'challenge')


class ChallengeCommentVote(models.Model):
    VALUE_CHOICES = [
        (1, 'Like'),
        (-1, 'Dislike')
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='challenge_comment_votes',
        db_index=True
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    comment = models.ForeignKey(ChallengeComment, on_delete=models.CASCADE, related_name='votes')
    value = models.SmallIntegerField(choices=VALUE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'comment')
        db_table = 'core_challengecommentvote'
