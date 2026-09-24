from rest_framework import serializers

from .models import Notification


# --- OKUMA (READ) SERIALIZERS ---

class NotificationSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True, allow_null=True, default=None)
    word_text = serializers.CharField(source='word.word', read_only=True, allow_null=True, default=None)
    word_def = serializers.CharField(source='word.definition', read_only=True, allow_null=True, default=None)
    word_example = serializers.CharField(source='word.example', read_only=True, allow_null=True, default=None)
    word_etymology = serializers.CharField(source='word.etymology', read_only=True, allow_null=True, default=None)

    # Challenge-comment notifications (challenge_like / challenge_dislike)
    challenge_comment_id = serializers.IntegerField(read_only=True, allow_null=True)
    challenge_id = serializers.SerializerMethodField()
    challenge_foreign_word = serializers.SerializerMethodField()
    challenge_meaning = serializers.SerializerMethodField()
    challenge_timer_on = serializers.SerializerMethodField()
    challenge_is_closed = serializers.SerializerMethodField()
    challenge_time_remaining_seconds = serializers.SerializerMethodField()
    challenge_suggested_word = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'actor_username',
            'word_text', 'word_def', 'word_example', 'word_etymology',
            'message', 'is_read', 'timestamp', 'word_id', 'comment_id',
            'challenge_comment_id', 'challenge_id', 'challenge_foreign_word',
            'challenge_meaning', 'challenge_timer_on', 'challenge_is_closed',
            'challenge_time_remaining_seconds', 'challenge_suggested_word',
        ]

    def _challenge(self, obj):
        cc = getattr(obj, 'challenge_comment', None)
        return cc.challenge if cc else None

    def get_challenge_id(self, obj):
        ch = self._challenge(obj)
        return ch.id if ch else None

    def get_challenge_foreign_word(self, obj):
        ch = self._challenge(obj)
        return ch.foreign_word if ch else None

    def get_challenge_meaning(self, obj):
        ch = self._challenge(obj)
        return ch.meaning if ch else None

    def get_challenge_timer_on(self, obj):
        ch = self._challenge(obj)
        return ch.timer_on if ch else None

    def get_challenge_is_closed(self, obj):
        ch = self._challenge(obj)
        return ch.is_closed if ch else None

    def get_challenge_time_remaining_seconds(self, obj):
        ch = self._challenge(obj)
        if ch is None:
            return None
        remaining = ch.time_remaining
        if remaining is not None:
            return int(remaining.total_seconds())
        return None

    def get_challenge_suggested_word(self, obj):
        cc = getattr(obj, 'challenge_comment', None)
        return cc.suggested_word if cc else None
