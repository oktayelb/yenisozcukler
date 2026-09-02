from rest_framework import serializers

from core.serializers import clean_text, clean_word
from .models import TranslationChallenge, ChallengeComment


class TranslationChallengeSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='display_author', read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    timer_on = serializers.BooleanField(read_only=True)
    timer_started_at = serializers.DateTimeField(read_only=True)
    is_closed = serializers.BooleanField(read_only=True)
    time_remaining_seconds = serializers.SerializerMethodField()
    winner = serializers.SerializerMethodField()

    class Meta:
        model = TranslationChallenge
        fields = [
            'id', 'foreign_word', 'meaning', 'author', 'timestamp',
            'comment_count', 'timer_on', 'timer_started_at', 'is_closed',
            'time_remaining_seconds', 'winner',
        ]

    def get_time_remaining_seconds(self, obj):
        remaining = obj.time_remaining
        if remaining is not None:
            return int(remaining.total_seconds())
        return None

    def get_winner(self, obj):
        if not obj.is_closed:
            return None
            
        # P1 FIX: Utilize the prefetched comments list if available to avoid N+1 queries.
        if hasattr(obj, 'prefetched_ordered_comments'):
            ordered_comments = obj.prefetched_ordered_comments
            top = ordered_comments[0] if ordered_comments else None
        else:
            top = obj.comments.order_by('-score', 'timestamp').first()

        if top and top.score > 0:
            return {
                'suggested_word': top.suggested_word,
                'author': top.display_author,
                'score': top.score,
            }
        return None


class TranslationChallengeCreateSerializer(serializers.Serializer):
    foreign_word = serializers.CharField(max_length=100, required=True)
    meaning = serializers.CharField(max_length=300, required=True)

    def validate_foreign_word(self, value):
        return clean_word(value, "Yabancı sözcük", 100, latin_only=False)

    def validate_meaning(self, value):
        return clean_text(value, "Anlam açıklaması", 300)


class ChallengeCommentSerializer(serializers.ModelSerializer):
    score = serializers.IntegerField(read_only=True)
    user_vote = serializers.SerializerMethodField()
    author = serializers.CharField(source='display_author', read_only=True)

    class Meta:
        model = ChallengeComment
        fields = [
            'id', 'challenge', 'author', 'suggested_word', 'etymology',
            'example_sentence', 'timestamp', 'score', 'user_vote',
        ]

    def get_user_vote(self, obj):
        votes = self.context.get('user_votes', {})
        vote_value = votes.get(obj.id)
        if vote_value == 1: return 'like'
        if vote_value == -1: return 'dislike'
        return None


class ChallengeSuggestionCreateSerializer(serializers.Serializer):
    challenge_id = serializers.IntegerField(required=True)
    suggested_word = serializers.CharField(max_length=30, required=True)
    etymology = serializers.CharField(max_length=200, required=True)
    example_sentence = serializers.CharField(max_length=200, required=True)

    def validate_suggested_word(self, value):
        return clean_word(value, "Önerilen sözcük", 30)

    def validate_etymology(self, value):
        return clean_text(value, "Köken bilgisi", 200)

    def validate_example_sentence(self, value):
        return clean_text(value, "Örnek cümle", 200)
