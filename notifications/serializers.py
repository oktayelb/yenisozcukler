from rest_framework import serializers

from .models import Notification


# --- OKUMA (READ) SERIALIZERS ---

class NotificationSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True, allow_null=True, default=None)
    word_text = serializers.CharField(source='word.word', read_only=True, allow_null=True, default=None)
    word_def = serializers.CharField(source='word.definition', read_only=True, allow_null=True, default=None)
    word_example = serializers.CharField(source='word.example', read_only=True, allow_null=True, default=None)
    word_etymology = serializers.CharField(source='word.etymology', read_only=True, allow_null=True, default=None)

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'actor_username',
            'word_text', 'word_def', 'word_example', 'word_etymology',
            'message', 'is_read', 'timestamp', 'word_id', 'comment_id',
        ]
